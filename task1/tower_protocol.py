from gradysim.protocol.messages.communication import CommunicationCommand, CommunicationCommandType
from node_protocol import NodeProtocol
import logging, constants

class TowerProtocol (NodeProtocol):

    # Inicialização
    def initialize(self):
        super().initialize()
        self.defaultColor = constants.TOWER_COLOR # Cor default da torre
        self.currentColor = constants.TOWER_COLOR
        self.scheduleSendQuestionTimer()

    def handle_packet(self, message):
        if "[RESPOSTA]" not in message:
            return
        closingBracket = message.find("]")
        try:
            senderLevel = int(message[1:closingBracket])
        except (ValueError, IndexError):
            logging.error(f"Resposta sem nível válido: {message}")
            return
        if senderLevel != 1: # A torre deve receber a resposta da camada imediatamente superior
            return
        self.received += 1
        self.messageReceivedType = constants.ANSWER_RECEIVED

    # Tick dos relógios
    def handle_timer(self, timer):
        super().handle_timer(timer) 
        if timer == "communication":
            self.sendQuestion()

    def sendQuestion(self):
        command = CommunicationCommand(CommunicationCommandType.BROADCAST, 
            message="[0][PERGUNTA] Quem vai ganhar a eleição para presidente?"
        )
        self.provider.send_communication_command(command)
        self.sent += 1
        self.scheduleSendQuestionTimer()

    def scheduleSendQuestionTimer(self):
        self.provider.schedule_timer(
            "communication",
            self.provider.current_time() + constants.SEND_QUESTION_INTERVAL
        )