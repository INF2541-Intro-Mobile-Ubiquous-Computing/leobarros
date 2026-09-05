from gradysim.protocol.messages.communication import CommunicationCommand, CommunicationCommandType
from visible_node_protocol import VisibleNodeProtocol
import logging, constants, shared

class TowerProtocol (VisibleNodeProtocol):

    # Inicialização
    def initialize(self):
        super().initialize()
        self.color = constants.RED # Cor default da torre
        #TODO shared.scheduleSendQuestionTimer(self)

    # Recebimento de mensagens
    def handle_packet(self, message):
        pass
        #TODO 
        # logging.info(f"Mensagem recebida num.{self.received}: {message}")
        # self.receivedFromLastTimerTick = constants.MESSAGE_RECEIVED_FROM_DRONE # Obrigatoriamente a torre recebeu de um drone
        # self.received += 1

    # Tick dos relógios
    # def handle_timer(self, timer):
    #     if timer == "appearance":
    #         self.setColorAndSize()
    #         #TODO 
        # elif timer == "communication":
        #     self.sendQuestion()

    def sendQuestion(self):
        command = CommunicationCommand(
                CommunicationCommandType.BROADCAST,
                message="[PERGUNTA] Quem vai ganhar a eleição para presidente?"
            )
        self.provider.send_communication_command(command)
        self.sent += 1
        logging.info("Torre enviou pergunta")
        shared.scheduleSendQuestionTimer(self)
