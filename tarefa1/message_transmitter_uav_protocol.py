import logging
import json

from gradysim.protocol.messages.communication import CommunicationCommand, CommunicationCommandType

import constants
from movable_core_uav_protocol import MovableCoreUAVProtocol


class MessageTransmitterUAVProtocol(MovableCoreUAVProtocol):
    """Encaminha pelo menor caminho do anel até o alvo do externo destinatário."""

    def handle_packet(self, message):
        node_index = self.provider.get_id()
        try:
            packet = json.loads(message)
            if not isinstance(packet, dict):
                raise ValueError('O envelope deve ser um objeto JSON.')
            if not isinstance(packet.get('message_id'), str) or not packet['message_id']:
                raise ValueError('Identificador de mensagem ausente ou inválido.')
            if not isinstance(packet.get('payload'), str):
                raise ValueError('Conteúdo ausente ou inválido.')
            self.flight_plan.get_core_target(packet.get('source_external_index'))
            destination = self.flight_plan.get_core_target(packet.get('destination_external_index'))
        except (ValueError, TypeError) as error:
            logging.warning('Mensagem descartada no core %s: %s', node_index, error)
            return

        if node_index == destination:
            logging.info('Mensagem %s recebida no core alvo %s: externo %s -> externo %s; conteúdo: %s',
                         packet['message_id'], node_index, packet['source_external_index'],
                         packet['destination_external_index'], packet['payload'])
            return

        increasing = (destination - node_index) % constants.DRONE_COUNT
        decreasing = (node_index - destination) % constants.DRONE_COUNT
        # Em empate (core par), prefere índices crescentes.
        step = 1 if increasing <= decreasing else -1
        next_hop = (node_index + step) % constants.DRONE_COUNT
        logging.info('Mensagem %s no core %s: encaminhando para %s, alvo final %s',
                     packet['message_id'], node_index, next_hop, destination)
        self.provider.send_communication_command(CommunicationCommand(
            CommunicationCommandType.SEND, message, next_hop
        ))
