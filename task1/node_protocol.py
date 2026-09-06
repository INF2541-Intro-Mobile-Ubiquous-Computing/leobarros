from gradysim.protocol.interface import IProtocol
from gradysim.simulator.extension.visualization_controller import VisualizationController
import constants, logging

class NodeProtocol (IProtocol):
    sent: int
    received: int
    messageReceivedType: int
    defaultColor = constants.BLACK
    currentColor = constants.BLACK

    def initialize(self):
        self.sent = 0
        self.received = 0
        self.messageReceivedType = constants.NO_MESSAGE_RECEIVED
        self.visualization = VisualizationController(self)
        self.scheduleAppearanceTimer()
    # Recebimento de mensagens
    def handle_packet(self, message):
        pass
        
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
        if self.messageReceivedType == constants.ANSWER_RECEIVED:
            self.currentColor = constants.BLUE
        if self.messageReceivedType == constants.QUESTION_RECEIVED:
            self.currentColor = constants.RED
        self.visualization.paint_node(self.provider.get_id(), self.currentColor)
        self.visualization.resize_nodes(constants.DEFAULT_SIZE) # TODO chamar uma vez só
        self.messageReceivedType = constants.NO_MESSAGE_RECEIVED
        self.currentColor = self.defaultColor
        self.scheduleAppearanceTimer()

    def scheduleAnswer():
        pass