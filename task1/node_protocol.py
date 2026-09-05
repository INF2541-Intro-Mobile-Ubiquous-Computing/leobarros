from gradysim.protocol.interface import IProtocol
from gradysim.simulator.extension.visualization_controller import VisualizationController
import constants, logging

class NodeProtocol (IProtocol):
    sent: int
    received: int
    messageReceivedType: int
    size: int
    defaultColor = constants.BLACK
    currentColor = constants.BLACK

    def initialize(self):
        self.sent = 0
        self.received = 0
        self.messageReceivedType = constants.NO_MESSAGE_RECEIVED
        self.size = constants.DEFAULT_SIZE
        self.visualization = VisualizationController(self)
        self.scheduleAppearanceTimer()

    # Recebimento de mensagens
    def handle_packet(self, message):
        self.received += 1
        if message.startswith("[PERGUNTA]"):
            self.messageReceivedType = constants.QUESTION_RECEIVED
            self.sendAnswer()
        elif message.startswith("[RESPOSTA]"):
            self.messageReceivedType = constants.ANSWER_RECEIVED
        # self.forwardMessage(message)
        
    # Recebimento de telemetria
    def handle_telemetry(self, telemetry):
        pass
    
    # Tick dos relógios
    def handle_timer(self, timer):
        if timer == "appearance":
            self.setColorAndSize()
    
    # Finalização do objeto
    def finish(self):
        logging.info(f"Mensagens: "
            f"Enviadas={self.sent} ; Recebidas={self.received}")

    def scheduleAppearanceTimer(self):
        self.provider.schedule_timer(
            "appearance",
            self.provider.current_time() + constants.REPAINT_INTERVAL
        )

    def setColorAndSize(self):
        #logging.debug(f"Mensagem recebida no último ciclo: {self.receivedFromLastCycle}")
        if self.messageReceivedType == constants.ANSWER_RECEIVED:
            self.currentColor = constants.BLUE
            self.size = constants.SIZE_WHEN_RECEIVING_MESSAGE
        if self.messageReceivedType == constants.QUESTION_RECEIVED:
            self.currentColor = constants.RED
            self.size = constants.SIZE_WHEN_RECEIVING_MESSAGE
        self.visualization.paint_node(self.provider.get_id(), self.currentColor)
        self.visualization.resize_nodes(self.size)
        self.messageReceivedType = constants.NO_MESSAGE_RECEIVED
        self.size = constants.DEFAULT_SIZE
        self.currentColor = self.defaultColor
        self.scheduleAppearanceTimer()