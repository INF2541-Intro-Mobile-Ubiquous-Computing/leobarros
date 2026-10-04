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

    def handle_packet(self, message):
        if self.handleHello(message):
            return
        if "[RESPOSTA]" not in message:
            return
        if not self.acceptMessage(message):
            return
        self.received += 1
        self.messageReceivedType = constants.ANSWER_RECEIVED
        self.lastResponse = message.split("[RESPOSTA]", 1)[1].strip()

    # Tick dos relógios
    def handle_timer(self, timer):
        super().handle_timer(timer) 
        if timer == "communication":
            self.sendQuestion()

    def sendQuestion(self):
        self.scheduleForwardMessage(
            self.createMessage("[PERGUNTA] Quem vai ganhar a eleição para presidente?")
        )
        self.scheduleSendQuestionTimer()

    def scheduleSendQuestionTimer(self):
        self.provider.schedule_timer(
            "communication",
            self.provider.current_time() + constants.SEND_QUESTION_INTERVAL
        )

    def finish(self):
        super().finish()
        logging.info(f"O próximo presidente do Brasil será: {self.lastResponse}")
