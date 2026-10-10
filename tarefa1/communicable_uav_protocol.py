import logging
import json
import math

from gradysim.protocol.messages.communication import CommunicationCommand, CommunicationCommandType

from movable_external_uav_protocol import MovableExternalUAVProtocol
from communication_packets import validate_data_packet
from radio_discovery import RadioDiscoveryMixin, DISCOVERY_TYPES
import constants


class CommunicableUAVProtocol(RadioDiscoveryMixin, MovableExternalUAVProtocol):
    """Envia e recebe mensagens no encontro, aguardando a troca antes de partir."""

    @classmethod
    def with_external(cls, index):
        class ConfiguredExternalUAV(cls):
            external_index = index

        return ConfiguredExternalUAV

    def initialize(self):
        self.initialize_discovery()
        if self.external_index not in constants.EXTERNAL_DESTINATIONS:
            raise ValueError('Configure o índice externo e seu destinatário fixo.')
        self.destination_external_index = constants.EXTERNAL_DESTINATIONS[self.external_index]
        self.message_sequence = 0
        self.received_messages = {}
        for value in (constants.EXTERNAL_CONTACT_TIMEOUT, constants.EXTERNAL_CONTACT_RETRY_INTERVAL):
            if not math.isfinite(value) or value <= 0:
                raise ValueError('Os intervalos de contato devem ser positivos e finitos.')
        super().initialize()
        self.flight_plan.get_core_target(self.destination_external_index)

    def start_away(self, now):
        if self.mode == 'contact':
            return
        if self.in_contact(now):
            if constants.SIMULATION_MODE == constants.RANDOM and not self.radio_contact_confirmed:
                self.begin_discovery(now)
                return
            self.message_sequence += 1
            self.mode = 'contact'
            self.record_metric('contact_started', external_index=self.external_index,
                               session_id=self.message_sequence)
            self.contact_until = now + constants.EXTERNAL_CONTACT_TIMEOUT
            self.steer(self.contact_position(now + constants.MOVEMENT_INTERVAL), now)
            packet = {
                'type': 'data',
                'message_id': f'{self.external_index}:{self.message_sequence}',
                'source_external_index': self.external_index,
                'source_color': self.color,
                'destination_external_index': self.destination_external_index,
                'payload': 'o pato',
            }
            message = json.dumps(packet)
            self.record_metric('emitted', packet)
            self.record_metric('transmission', packet, kind='data')
            self.provider.send_communication_command(CommunicationCommand(
                CommunicationCommandType.SEND, message, self.target_index
            ))
            logging.info('Mensagem %s enviada: externo %s -> externo %s via core %s',
                         packet['message_id'], self.external_index,
                         self.destination_external_index, self.target_index)
            self.send_presence(now)
            return
        super().start_away(now)

    def send_contact_packet(self, kind, **fields):
        packet = dict(type=kind, external_index=self.external_index,
                      node_id=self.provider.get_id(), session_id=self.message_sequence, **fields)
        self.record_metric('transmission', packet, kind=kind)
        self.provider.send_communication_command(CommunicationCommand(
            CommunicationCommandType.SEND, json.dumps(packet), self.target_index))

    def send_presence(self, now):
        self.send_contact_packet('presence')
        self.next_presence_at = min(now + constants.EXTERNAL_CONTACT_RETRY_INTERVAL, self.contact_until)
        self.provider.schedule_timer(constants.CONTACT_TIMER, self.next_presence_at)

    def handle_timer(self, timer):
        now = self.provider.current_time()
        if constants.SIMULATION_MODE == constants.RANDOM and self.discovery_timer(timer, now):
            return
        if timer == constants.CONTACT_TIMER:
            if self.mode != 'contact':
                return
            if now >= self.contact_until:
                self.record_metric('contact_timeout', external_index=self.external_index,
                                   session_id=self.message_sequence)
                logging.debug('Tempo de contato esgotado para externo %s', self.external_index)
                self.radio_contact_confirmed = False
                self.mini_plan = None
                super().start_away(now)
            elif now >= self.next_presence_at:
                if self.in_contact(now):
                    self.send_presence(now)
                else:
                    self.next_presence_at = min(now + constants.EXTERNAL_CONTACT_RETRY_INTERVAL,
                                                self.contact_until)
                    self.provider.schedule_timer(constants.CONTACT_TIMER, self.next_presence_at)
            return
        if timer == constants.MOVEMENT_TIMER and self.mode == 'contact':
            self.steer(self.contact_position(now + constants.MOVEMENT_INTERVAL), now)
            self.schedule_movement_timer()
            return
        super().handle_timer(timer)

    def handle_packet(self, message):
        try:
            response = json.loads(message)
            if (constants.SIMULATION_MODE == constants.RANDOM and isinstance(response, dict)
                    and response.get('type') in DISCOVERY_TYPES):
                self.handle_discovery(response)
                return
            if (constants.SIMULATION_MODE == constants.RANDOM and isinstance(response, dict)
                    and response.get('type', 'data') == 'data'):
                # Ouvir o broadcast do core não substitui a entrega confirmada no encontro.
                validate_data_packet(response, self.flight_plan)
                return
            if not isinstance(response, dict) or response.get('type') not in ('delivery', 'contact_complete'):
                raise ValueError('Resposta de contato inválida.')
            if (type(response.get('external_index')) is not int
                    or type(response.get('core_id')) is not int
                    or type(response.get('session_id')) is not int):
                raise ValueError('Identificação de contato inválida.')
            if (self.mode != 'contact' or response['external_index'] != self.external_index
                    or response['core_id'] != self.target_index
                    or response['session_id'] != self.message_sequence):
                return
            if response['type'] == 'contact_complete':
                self.record_metric('contact_completed', external_index=self.external_index,
                                   session_id=self.message_sequence)
                self.radio_contact_confirmed = False
                self.mini_plan = None
                super().start_away(self.provider.current_time())
                return
            packet = response.get('packet')
            _, source_color = validate_data_packet(packet, self.flight_plan)
            if packet['destination_external_index'] != self.external_index:
                raise ValueError('Entrega dirigida a outro externo.')
        except (ValueError, TypeError) as error:
            logging.warning('Mensagem descartada no externo %s: %s', self.external_index, error)
            return
        self.show_message_color(source_color)
        message_id = packet['message_id']
        if message_id not in self.received_messages:
            self.received_messages[message_id] = packet
            self.record_metric('received', packet)
            logging.info('Mensagem %s recebida no externo %s; conteúdo: %s',
                         message_id, self.external_index, packet['payload'])
        # Confirma também as retransmissões, caso o ACK anterior tenha se perdido.
        self.send_contact_packet('ack', message_id=message_id)
