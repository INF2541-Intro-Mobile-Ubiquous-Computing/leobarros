from node_protocol import NodeProtocol
import logging, constants

class TowerProtocol (NodeProtocol):

    # Inicialização
    def initialize(self):
        super().initialize()
        self.defaultColor = constants.TOWER_COLOR # Cor default da torre
        self.currentColor = constants.TOWER_COLOR
        self.lastResponse = None
        self.scheduleSendQuestionTimer()

    def deliverMessage(self, packet):
        if packet["type"] == "RESPOSTA":
            self.lastResponse = packet["text"]

    # Tick dos relógios
    def handle_timer(self, timer):
        super().handle_timer(timer) 
        if timer == "communication":
            self.sendQuestion()

    def sendQuestion(self):
        if self.current_position is not None:
            x, y, _ = self.current_position
            self.sendMessage("PERGUNTA", "Quem vai ganhar a eleição para presidente?",
                             constants.GEOCAST_REGION, (x, x, y, y))
        self.scheduleSendQuestionTimer()

    def scheduleSendQuestionTimer(self):
        self.provider.schedule_timer(
            "communication",
            self.provider.current_time() + constants.SEND_QUESTION_INTERVAL
        )

    def finish(self):
        super().finish()
        logging.info(f"O próximo presidente do Brasil será: {self.lastResponse}")