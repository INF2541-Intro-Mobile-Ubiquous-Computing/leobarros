import logging
import json

from gradysim.protocol.messages.communication import CommunicationCommand, CommunicationCommandType

from movable_external_uav_protocol import MovableExternalUAVProtocol
import constants


class CommunicableUAVProtocol(MovableExternalUAVProtocol):
    """Envia uma mensagem ao alvo a cada encontro, antes de se afastar."""

    @classmethod
    def with_external(cls, index):
        class ConfiguredExternalUAV(cls):
            external_index = index

        return ConfiguredExternalUAV

    def initialize(self):
        if self.external_index not in constants.EXTERNAL_DESTINATIONS:
            raise ValueError('Configure o índice externo e seu destinatário fixo.')
        self.destination_external_index = constants.EXTERNAL_DESTINATIONS[self.external_index]
        self.message_sequence = 0
        super().initialize()
        self.flight_plan.get_core_target(self.destination_external_index)

    def start_away(self, now):
        if self.in_contact(now):
            self.message_sequence += 1
            packet = {
                'message_id': f'{self.external_index}:{self.message_sequence}',
                'source_external_index': self.external_index,
                'destination_external_index': self.destination_external_index,
                'payload': 'o pato',
            }
            message = json.dumps(packet)
            self.provider.send_communication_command(CommunicationCommand(
                CommunicationCommandType.SEND, message, self.target_index
            ))
            logging.info('Mensagem %s enviada: externo %s -> externo %s via core %s',
                         packet['message_id'], self.external_index,
                         self.destination_external_index, self.target_index)
        super().start_away(now)
