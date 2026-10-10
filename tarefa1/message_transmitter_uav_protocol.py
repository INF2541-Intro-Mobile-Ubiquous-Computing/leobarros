import logging
import json

from gradysim.protocol.messages.communication import CommunicationCommand, CommunicationCommandType

import constants
from movable_core_uav_protocol import MovableCoreUAVProtocol
from communication_packets import validate_contact_packet, validate_data_packet


class MessageTransmitterUAVProtocol(MovableCoreUAVProtocol):
    """Encaminha pelo menor caminho do anel até o alvo do externo destinatário."""

    def initialize(self):
        self.pending_messages = {}
        self.confirmed_messages = set()
        self.contacts = {}
        super().initialize()

    def handle_packet(self, message):
        node_index = self.provider.get_id()
        try:
            packet = json.loads(message)
            if not isinstance(packet, dict):
                raise ValueError('O envelope deve ser um objeto JSON.')
            if packet.get('type') in ('presence', 'ack'):
                self.handle_contact_packet(packet)
                return
            destination, source_color = validate_data_packet(packet, self.flight_plan)
        except (ValueError, TypeError) as error:
            logging.warning('Mensagem descartada no core %s: %s', node_index, error)
            return

        self.show_message_color(source_color)

        if node_index == destination:
            self.record_metric('core_arrival', packet)
            if packet['message_id'] not in self.confirmed_messages:
                self.pending_messages.setdefault(packet['message_id'], packet)
            logging.debug('Mensagem %s recebida no core alvo %s: externo %s -> externo %s; conteúdo: %s',
                         packet['message_id'], node_index, packet['source_external_index'],
                         packet['destination_external_index'], packet['payload'])
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
        if target != self.provider.get_id():
            raise ValueError('Contato dirigido ao core errado.')
        session_id = packet['session_id']
        contact = self.contacts.get(external)
        if packet['type'] == 'presence':
            if contact is not None and session_id < contact['session_id']:
                return
            if contact is None or session_id > contact['session_id']:
                contact = dict(session_id=session_id, node_id=packet['node_id'], offered=set())
                self.contacts[external] = contact
            elif contact['node_id'] != packet['node_id']:
                raise ValueError('ID externo diferente durante a mesma sessão.')
            self.send_pending(external, contact)
        else:
            message_id = packet.get('message_id')
            if not isinstance(message_id, str) or not message_id:
                raise ValueError('Confirmação sem identificador de mensagem válido.')
            if (contact is None or session_id != contact['session_id']
                    or packet['node_id'] != contact['node_id']
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
        response = dict(type=kind, external_index=external, core_id=self.provider.get_id(),
                        session_id=contact['session_id'], **fields)
        self.record_metric('transmission', fields.get('packet'), kind=kind)
        self.provider.send_communication_command(CommunicationCommand(
            CommunicationCommandType.SEND, json.dumps(response), contact['node_id']))
