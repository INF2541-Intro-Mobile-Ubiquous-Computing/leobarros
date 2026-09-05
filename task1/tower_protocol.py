from gradysim.protocol.messages.communication import CommunicationCommand, CommunicationCommandType
from node_protocol import NodeProtocol
import logging, constants

class TowerProtocol (NodeProtocol):

    # Inicialização
    def initialize(self):
        super().initialize()
        self.defaultColor = constants.RED # Cor default da torre
        self.currentColor = constants.RED
        self.scheduleSendQuestionTimer()

    # Tick dos relógios
    def handle_timer(self, timer):
        super().handle_timer(timer) 
        if timer == "communication":
            self.sendQuestion()

    def sendQuestion(self):
        command = CommunicationCommand(CommunicationCommandType.BROADCAST, 
            message="[PERGUNTA] Quem vai ganhar a eleição para presidente?"
        )
        self.provider.send_communication_command(command)
        self.sent += 1
        # logging.info("Torre enviou pergunta")
        self.scheduleSendQuestionTimer()

    def scheduleSendQuestionTimer(self):
        self.provider.schedule_timer(
            "communication",
            self.provider.current_time() + constants.SEND_QUESTION_INTERVAL
        )