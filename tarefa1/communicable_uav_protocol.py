import logging

from gradysim.protocol.messages.communication import CommunicationCommand, CommunicationCommandType

from movable_external_uav_protocol import MovableExternalUAVProtocol


class CommunicableUAVProtocol(MovableExternalUAVProtocol):
    """Envia uma mensagem ao alvo a cada encontro, antes de se afastar."""

    def start_away(self, now):
        if self.in_contact(now):
            message = "o pato"
            self.provider.send_communication_command(CommunicationCommand(
                CommunicationCommandType.SEND, message, self.target_index
            ))
            logging.info("Mensagem enviada: %s", message)
        super().start_away(now)
