import logging, constants
from horizontal_uav_protocol import HorizontalUAVProtocol
from gradysim.protocol.messages.communication import CommunicationCommand, CommunicationCommandType

class FinalUAVProtocol(HorizontalUAVProtocol):

    def handle_packet(self, message):
        senderLevel = self.getSenderLevel(message)
        if senderLevel is None:
            logging.error(f"Mensagem sem nível: {message}")
            return
        if "[PERGUNTA]" not in message:
            return
        if senderLevel >= self.level: # O drone final responde somente a perguntas vindas de níveis inferiores.
            return
        self.received += 1
        self.messageReceivedType = constants.QUESTION_RECEIVED
        response = f"[{self.level}][RESPOSTA] E eu sei lá, ué"
        command = CommunicationCommand(CommunicationCommandType.BROADCAST, response)
        self.provider.send_communication_command(command) # A resposta é imediata, aproveitando a proximidade do outro drone
        self.sent += 1