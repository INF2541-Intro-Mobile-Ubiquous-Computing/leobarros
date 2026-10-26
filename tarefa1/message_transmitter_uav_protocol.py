import logging
import json
import math

from gradysim.protocol.messages.communication import CommunicationCommand, CommunicationCommandType

import constants
from movable_core_uav_protocol import MovableCoreUAVProtocol
from communication_packets import validate_contact_packet, validate_data_packet


class MessageTransmitterUAVProtocol(MovableCoreUAVProtocol):
    """Encaminha pelo anel em TOPOLOGY e por inundação em RANDOM."""

    def initialize(self):
        self.pending_messages = {}
        self.confirmed_messages = set()
        self.contacts = {}
        self.seen_messages = set()
        super().initialize()

    def handle_packet(self, message):
        node_index = self.provider.get_id()
        try:
            packet = json.loads(message)
            if not isinstance(packet, dict):
                raise ValueError('O envelope deve ser um objeto JSON.')
            if packet.get('type') == 'station_request':
                self.handle_station_request(packet)
                return
            if packet.get('type') == 'contact_relay':
                self.handle_relay(packet)
                return
            if packet.get('type') in ('presence', 'ack'):
                self.handle_contact_packet(packet)
                return
            destination, source_color = validate_data_packet(packet, self.flight_plan)
        except (ValueError, TypeError) as error:
            logging.warning('Mensagem descartada no core %s: %s', node_index, error)
            return

        if constants.SIMULATION_MODE == constants.RANDOM:
            if packet['message_id'] in self.seen_messages:
                return
            self.seen_messages.add(packet['message_id'])
        self.show_message_color(source_color)

        if node_index == destination:
            self.record_metric('core_arrival', packet)
            if packet['message_id'] not in self.confirmed_messages:
                self.pending_messages.setdefault(packet['message_id'], packet)
            logging.debug('Mensagem %s recebida no core alvo %s: externo %s -> externo %s; conteúdo: %s',
                         packet['message_id'], node_index, packet['source_external_index'],
                         packet['destination_external_index'], packet['payload'])
            return

        if constants.SIMULATION_MODE == constants.RANDOM:
            logging.debug('Mensagem %s no core %s: retransmitindo em broadcast, alvo %s',
                          packet['message_id'], node_index, destination)
            self.record_metric('transmission', packet, kind='data')
            self.provider.send_communication_command(CommunicationCommand(
                CommunicationCommandType.BROADCAST, message))
            return

        increasing = (destination - node_index) % constants.DRONE_COUNT
        decreasing = (node_index - destination) % constants.DRONE_COUNT
        # Em empate (core par), prefere índices crescentes.
        step = 1 if increasing <= decreasing else -1
        next_hop = (node_index + step) % constants.DRONE_COUNT
        logging.debug('Mensagem %s no core %s: encaminhando para %s, alvo final %s',
                     packet['message_id'], node_index, next_hop, destination)
        self.record_metric('transmission', packet, kind='data')
        self.provider.send_communication_command(CommunicationCommand(
            CommunicationCommandType.SEND, message, next_hop
        ))

    def handle_contact_packet(self, packet):
        external, target = validate_contact_packet(packet, self.flight_plan)
        relay = packet.get('relay_core', target)
        if type(relay) is not int or not 0 <= relay < constants.DRONE_COUNT:
            raise ValueError('Core de contato inválido.')
        if target != self.provider.get_id():
            if relay != self.provider.get_id():
                raise ValueError('Contato dirigido ao core errado.')
            self.route_contact(target, packet)
            return
        session_id = packet['session_id']
        contact = self.contacts.get(external)
        if packet['type'] == 'presence':
            if contact is not None and session_id < contact['session_id']:
                return
            if contact is None or session_id > contact['session_id']:
                contact = dict(session_id=session_id, node_id=packet['node_id'], relay_core=relay, offered=set())
                self.contacts[external] = contact
            elif contact['node_id'] != packet['node_id'] or contact['relay_core'] != relay:
                raise ValueError('ID externo diferente durante a mesma sessão.')
            self.send_pending(external, contact)
        else:
            message_id = packet.get('message_id')
            if not isinstance(message_id, str) or not message_id:
                raise ValueError('Confirmação sem identificador de mensagem válido.')
            if (contact is None or session_id != contact['session_id']
                    or packet['node_id'] != contact['node_id'] or relay != contact['relay_core']
                    or message_id not in contact['offered']):
                return
            stored = self.pending_messages.get(message_id)
            if stored is None or stored['destination_external_index'] != external:
                return
            del self.pending_messages[message_id]
            self.confirmed_messages.add(message_id)
            self.record_metric('confirmed', stored)
            logging.debug('Mensagem %s confirmada pelo externo %s', message_id, external)
            if not any(p['destination_external_index'] == external
                       for p in self.pending_messages.values()):
                self.send_contact_response('contact_complete', external, contact)

    def send_pending(self, external, contact):
        pending = [packet for packet in self.pending_messages.values()
                   if packet['destination_external_index'] == external]
        for packet in pending:
            contact['offered'].add(packet['message_id'])
            self.send_contact_response('delivery', external, contact, packet=packet)
        if not pending:
            self.send_contact_response('contact_complete', external, contact)

    def send_contact_response(self, kind, external, contact, **fields):
        relay = contact['relay_core']
        response = dict(type=kind, external_index=external, core_id=relay,
                        session_id=contact['session_id'], **fields)
        if relay == self.provider.get_id():
            self.record_metric('transmission', fields.get('packet'), kind=kind)
            self.provider.send_communication_command(CommunicationCommand(
                CommunicationCommandType.SEND, json.dumps(response), contact['node_id']))
        else:
            self.route_contact(relay, response, contact['node_id'])

    def handle_station_request(self, packet):
        self.flight_plan.get_core_target(packet.get('external_index'))
        if (type(packet.get('node_id')) is not int or packet['node_id'] < constants.DRONE_COUNT
                or not isinstance(packet.get('request_id'), str)):
            raise ValueError('Solicitação de encontro inválida.')
        expiry = packet.get('expires_at')
        position = packet.get('position')
        if (type(expiry) not in (int, float) or not math.isfinite(expiry)
                or not isinstance(position, (list, tuple)) or len(position) != 3
                or any(type(x) not in (int, float) or not math.isfinite(x) for x in position)):
            raise ValueError('Posição ou prazo de encontro inválido.')
        if self.provider.current_time() >= expiry:
            return
        # Usa somente a própria telemetria e a posição anunciada pelo externo.
        own_position = getattr(self, 'current_position', None)
        if own_position is None or math.dist(own_position, position) > constants.EXTERNAL_CONTACT_DISTANCE:
            return
        response = dict(type='station_offer', request_id=packet['request_id'],
                        external_index=packet['external_index'], core_id=self.provider.get_id())
        self.record_metric('transmission', kind='station_offer')
        self.provider.send_communication_command(CommunicationCommand(
            CommunicationCommandType.SEND, json.dumps(response), packet['node_id']))

    def route_contact(self, target, packet, external_node_id=None):
        envelope = dict(type='contact_relay', target_core=target, packet=packet,
                        external_node_id=external_node_id, hops_left=constants.DRONE_COUNT,
                        expires_at=self.provider.current_time() + constants.EXTERNAL_CONTACT_TIMEOUT)
        self.handle_relay(envelope)

    def handle_relay(self, envelope):
        target = envelope.get('target_core')
        hops = envelope.get('hops_left')
        expiry = envelope.get('expires_at')
        packet = envelope.get('packet')
        if (type(target) is not int or not 0 <= target < constants.DRONE_COUNT
                or type(hops) is not int or not 0 <= hops <= constants.DRONE_COUNT
                or type(expiry) not in (int, float) or not math.isfinite(expiry)
                or not isinstance(packet, dict)
                or packet.get('type') not in ('presence', 'ack', 'delivery', 'contact_complete')):
            raise ValueError('Encaminhamento de contato inválido.')
        if self.provider.current_time() >= expiry:
            return
        node = self.provider.get_id()
        if node == target:
            if packet['type'] in ('presence', 'ack'):
                self.handle_contact_packet(packet)
            else:
                external = envelope.get('external_node_id')
                if type(external) is not int or external < constants.DRONE_COUNT:
                    raise ValueError('Destinatário externo inválido.')
                self.record_metric('transmission', packet.get('packet'), kind=packet['type'])
                self.provider.send_communication_command(CommunicationCommand(
                    CommunicationCommandType.SEND, json.dumps(packet), external))
            return
        if hops == 0:
            return
        if constants.SIMULATION_MODE == constants.TOPOLOGY:
            increasing = (target - node) % constants.DRONE_COUNT
            decreasing = (node - target) % constants.DRONE_COUNT
            next_hop = (node + (1 if increasing <= decreasing else -1)) % constants.DRONE_COUNT
        else:
            next_hop = target
        envelope = dict(envelope, hops_left=hops - 1)
        self.record_metric('transmission', kind='contact_relay')
        self.provider.send_communication_command(CommunicationCommand(
            CommunicationCommandType.SEND, json.dumps(envelope), next_hop))
