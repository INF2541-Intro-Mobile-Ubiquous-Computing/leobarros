import logging
import json
import math

from gradysim.protocol.messages.communication import CommunicationCommand, CommunicationCommandType

from movable_external_uav_protocol import MovableExternalUAVProtocol
from communication_packets import validate_data_packet
import constants


class CommunicableUAVProtocol(MovableExternalUAVProtocol):
    """Envia e recebe mensagens no encontro, aguardando a troca antes de partir."""

    @classmethod
    def with_external(cls, index):
        class ConfiguredExternalUAV(cls):
            external_index = index

        return ConfiguredExternalUAV

    def initialize(self):
        self.discovery_sequence = 0
        self.next_query_at = 0
        self.query_id = None
        self.query_deadline = 0
        if self.external_index not in constants.EXTERNAL_DESTINATIONS:
            raise ValueError('Configure o índice externo e seu destinatário fixo.')
        self.destination_external_index = constants.EXTERNAL_DESTINATIONS[self.external_index]
        self.message_sequence = 0
        self.received_messages = {}
        for value in (constants.EXTERNAL_CONTACT_TIMEOUT, constants.EXTERNAL_CONTACT_RETRY_INTERVAL,
                      constants.DISCOVERY_RESPONSE_TIMEOUT):
            if not math.isfinite(value) or value <= 0:
                raise ValueError('Os intervalos de contato devem ser positivos e finitos.')
        super().initialize()
        self.flight_plan.get_core_target(self.destination_external_index)

    def wait_for_core(self, now):
        if now < self.next_query_at:
            return
        self.discovery_sequence += 1
        self.query_id = f'{self.provider.get_id()}:station:{self.discovery_sequence}'
        self.query_deadline = now + constants.DISCOVERY_RESPONSE_TIMEOUT
        self.next_query_at = now + constants.EXTERNAL_CONTACT_RETRY_INTERVAL
        packet = dict(type='station_request', request_id=self.query_id,
                      external_index=self.external_index, node_id=self.provider.get_id(),
                      position=self.contact_point, expires_at=self.query_deadline)
        self.record_metric('discovery_started')
        self.record_metric('transmission', kind='station_request')
        self.provider.send_communication_command(CommunicationCommand(
            CommunicationCommandType.BROADCAST, json.dumps(packet)))

    def accept_offer(self, response):
        now = self.provider.current_time()
        core = response.get('core_id')
        if (self.mode != 'waiting' or not self.at_contact_point()
                or now >= self.query_deadline or response.get('request_id') != self.query_id
                or response.get('external_index') != self.external_index
                or type(core) is not int or not 0 <= core < constants.DRONE_COUNT):
            return
        self.target_index = core
        self.record_metric('discovery_contact_confirmed')
        self.start_contact(now)

    def start_contact(self, now):
        if self.mode != 'waiting' or self.target_index is None or not self.at_contact_point():
            return
        self.message_sequence += 1
        self.mode = 'contact'
        self.record_metric('contact_started', external_index=self.external_index,
                           session_id=self.message_sequence)
        self.contact_until = now + constants.EXTERNAL_CONTACT_TIMEOUT
        self.steer(self.contact_point, now)
        packet = dict(type='data', message_id=f'{self.external_index}:{self.message_sequence}',
                      source_external_index=self.external_index, source_color=self.color,
                      destination_external_index=self.destination_external_index, payload='o pato')
        self.record_metric('emitted', packet)
        self.record_metric('transmission', packet, kind='data')
        self.provider.send_communication_command(CommunicationCommand(
            CommunicationCommandType.SEND, json.dumps(packet), self.target_index))
        logging.info('Mensagem %s enviada: externo %s -> externo %s via core %s',
                     packet['message_id'], self.external_index,
                     self.destination_external_index, self.target_index)
        self.send_presence(now)

    def send_contact_packet(self, kind, **fields):
        packet = dict(type=kind, external_index=self.external_index,
                      node_id=self.provider.get_id(), session_id=self.message_sequence,
                      relay_core=self.target_index, **fields)
        self.record_metric('transmission', packet, kind=kind)
        self.provider.send_communication_command(CommunicationCommand(
            CommunicationCommandType.SEND, json.dumps(packet), self.target_index))

    def send_presence(self, now):
        self.send_contact_packet('presence')
        self.next_presence_at = min(now + constants.EXTERNAL_CONTACT_RETRY_INTERVAL, self.contact_until)
        self.provider.schedule_timer(constants.CONTACT_TIMER, self.next_presence_at)

    def handle_timer(self, timer):
        now = self.provider.current_time()
        if timer == constants.CONTACT_TIMER:
            if self.mode != 'contact':
                return
            if now >= self.contact_until:
                self.record_metric('contact_timeout', external_index=self.external_index,
                                   session_id=self.message_sequence)
                logging.debug('Tempo de contato esgotado para externo %s', self.external_index)
                super().start_away(now)
            elif now >= self.next_presence_at:
                self.send_presence(now)
            return
        super().handle_timer(timer)

    def handle_packet(self, message):
        try:
            response = json.loads(message)
            if isinstance(response, dict) and response.get('type') == 'station_offer':
                self.accept_offer(response)
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
