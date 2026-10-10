"""Descoberta por rádio e interceptação de um trecho de movimento anunciado."""

import json
import math

from gradysim.protocol.messages.communication import CommunicationCommand, CommunicationCommandType

import constants


DISCOVERY_TYPES = ('position_request', 'position_plan', 'contact_probe', 'contact_ready')


def validate_discovery(packet, flight_plan):
    if packet.get('type') not in DISCOVERY_TYPES:
        raise ValueError('Tipo de descoberta inválido.')
    if not isinstance(packet.get('request_id'), str) or not packet['request_id']:
        raise ValueError('Consulta sem identificador.')
    target = flight_plan.get_core_target(packet.get('external_index'))
    if type(packet.get('target_core')) is not int or packet['target_core'] != target:
        raise ValueError('Alvo de descoberta inválido.')
    if type(packet.get('requester_id')) is not int or packet['requester_id'] < constants.DRONE_COUNT:
        raise ValueError('Solicitante inválido.')
    expiry = packet.get('query_expires_at')
    if type(expiry) not in (int, float) or not math.isfinite(expiry):
        raise ValueError('Prazo de consulta inválido.')
    if packet['type'] in ('position_plan', 'contact_ready'):
        validate_mini_plan(packet.get('plan'))


def validate_mini_plan(plan):
    if not isinstance(plan, dict):
        raise ValueError('Mini plano ausente.')
    for field in ('reference_time', 'valid_until'):
        if type(plan.get(field)) not in (float, int) or not math.isfinite(plan[field]):
            raise ValueError('Instante do mini plano inválido.')
    if plan['valid_until'] <= plan['reference_time']:
        raise ValueError('Mini plano sem intervalo válido.')
    for field in ('relative_position', 'velocity'):
        vector = plan.get(field)
        if (not isinstance(vector, (list, tuple)) or len(vector) != 2
                or any(type(value) not in (int, float) or not math.isfinite(value) for value in vector)):
            raise ValueError('Vetor do mini plano inválido.')


def planned_position(plan, flight_plan, time):
    center = flight_plan.get_position(time)
    delay = time - plan['reference_time']
    return (center[0] + plan['relative_position'][0] + plan['velocity'][0] * delay,
            center[1] + plan['relative_position'][1] + plan['velocity'][1] * delay, center[2])


class RadioDiscoveryMixin:
    def initialize_discovery(self):
        self.discovery_sequence = 0
        self.discovery_request = None
        self.mini_plan = None
        self.radio_contact_confirmed = False
        for value in (constants.DISCOVERY_RESPONSE_TIMEOUT, constants.DISCOVERY_PROBE_TIMEOUT):
            if not math.isfinite(value) or value <= 0:
                raise ValueError('Prazos de descoberta devem ser positivos e finitos.')

    def send_discovery(self, packet, broadcast=True):
        self.record_metric('transmission', kind=packet['type'])
        self.provider.send_communication_command(CommunicationCommand(
            CommunicationCommandType.BROADCAST if broadcast else CommunicationCommandType.SEND,
            json.dumps(packet), None if broadcast else self.target_index))

    def begin_discovery(self, now):
        self.discovery_sequence += 1
        self.mode = 'query'
        self.radio_contact_confirmed = False
        self.mini_plan = None
        self.discovery_deadline = now + constants.DISCOVERY_RESPONSE_TIMEOUT
        self.discovery_request = dict(type='position_request',
            request_id=f'{self.provider.get_id()}:query:{self.discovery_sequence}',
            requester_id=self.provider.get_id(), external_index=self.external_index,
            target_core=self.target_index, query_expires_at=self.discovery_deadline)
        self.record_metric('discovery_started')
        self.send_discovery(self.discovery_request)
        self.provider.schedule_timer(constants.DISCOVERY_TIMER, self.discovery_deadline)
        self.steer(super().target_position(now + constants.MOVEMENT_INTERVAL), now)

    def fail_discovery(self, event, now):
        self.record_metric(event)
        self.mini_plan = None
        self.radio_contact_confirmed = False
        # Recomeça só após o afastamento e uma nova aproximação.
        super().start_away(now)

    def target_position(self, time):
        if constants.SIMULATION_MODE == constants.RANDOM and self.mini_plan is not None:
            bounded = min(max(time, self.mini_plan['reference_time']), self.mini_plan['valid_until'])
            return planned_position(self.mini_plan, self.flight_plan, bounded)
        return super().target_position(time)

    def in_contact(self, now):
        if constants.SIMULATION_MODE == constants.RANDOM:
            if self.radio_contact_confirmed:
                return True
            if self.mode in ('query', 'intercept', 'probe'):
                return False
        return super().in_contact(now)

    def handle_telemetry(self, telemetry):
        if constants.SIMULATION_MODE == constants.RANDOM and self.mode in ('query', 'intercept', 'probe'):
            self.current_position = telemetry.current_position
            return
        super().handle_telemetry(telemetry)

    def discovery_timer(self, timer, now):
        if self.mode not in ('query', 'intercept', 'probe'):
            return timer == constants.DISCOVERY_TIMER
        if timer not in (constants.DISCOVERY_TIMER, constants.MOVEMENT_TIMER):
            return False
        if now >= self.discovery_deadline:
            self.fail_discovery('discovery_no_response' if self.mode == 'query'
                                else 'discovery_intercept_failed', now)
        elif timer == constants.MOVEMENT_TIMER:
            if self.mode == 'query':
                self.steer(super().target_position(now + constants.MOVEMENT_INTERVAL), now)
            else:
                self.steer(self.target_position(self.intercept_time), now)
                if (self.mode == 'intercept' and now >= self.mini_plan['reference_time']
                        and math.dist(self.current_position, self.target_position(now)) <= constants.EXTERNAL_CONTACT_DISTANCE):
                    self.mode = 'probe'
                    self.discovery_deadline = min(self.mini_plan['valid_until'], now + constants.DISCOVERY_PROBE_TIMEOUT)
                    self.send_discovery(dict(self.discovery_request, type='contact_probe'), broadcast=False)
                    self.provider.schedule_timer(constants.DISCOVERY_TIMER, self.discovery_deadline)
        if timer == constants.MOVEMENT_TIMER:
            self.schedule_movement_timer()
        return True

    def handle_discovery(self, packet):
        validate_discovery(packet, self.flight_plan)
        if packet['type'] not in ('position_plan', 'contact_ready'):
            return
        if (self.discovery_request is None or packet['request_id'] != self.discovery_request['request_id']
                or packet['requester_id'] != self.provider.get_id()
                or packet['external_index'] != self.external_index or packet['target_core'] != self.target_index):
            return
        now = self.provider.current_time()
        if packet['type'] == 'contact_ready':
            if self.mode != 'probe' or now >= self.discovery_deadline:
                return
            self.radio_contact_confirmed = True
            self.record_metric('discovery_contact_confirmed')
            self.start_away(now)  # O protocolo comunicável inicia a troca de dados.
            return
        if self.mode != 'query':
            return
        if now >= self.discovery_deadline:
            self.fail_discovery('discovery_no_response', now)
            return
        plan = packet['plan']
        if now >= plan['valid_until']:
            self.fail_discovery('discovery_expired_response', now)
            return
        self.mini_plan = plan
        time = max(now, plan['reference_time'])
        while time < plan['valid_until']:
            distance = math.dist(self.current_position, planned_position(plan, self.flight_plan, time))
            if distance <= constants.EXTERNAL_SPEED * (time - now) + constants.EXTERNAL_CONTACT_DISTANCE:
                self.intercept_time = time
                self.mode = 'intercept'
                self.discovery_deadline = plan['valid_until']
                self.provider.schedule_timer(constants.DISCOVERY_TIMER, self.discovery_deadline)
                self.steer(self.target_position(time), now)
                return
            time += constants.EXTERNAL_INTERCEPT_STEP
        self.fail_discovery('discovery_intercept_failed', now)
