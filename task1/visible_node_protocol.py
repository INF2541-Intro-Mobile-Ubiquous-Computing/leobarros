from gradysim.protocol.interface import IProtocol
from gradysim.simulator.extension.visualization_controller import VisualizationController
import constants, logging

class VisibleNodeProtocol (IProtocol):
    sent: int
    received: int
    receivedFromLastTimerTick: int
    size: int

    def initialize(self):
        self.sent = 0
        self.received = 0
        self.receivedFromLastTimerTick = constants.NO_MESSAGE_RECEIVED
        self.size = constants.DEFAULT_SIZE
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
            self.provider.current_time() + constants.REDRAW_INTERVAL
        )

    def setColorAndSize(self):
        #logging.debug(f"Mensagem recebida no último ciclo: {self.receivedFromLastCycle}")
        if self.receivedFromLastTimerTick == constants.MESSAGE_RECEIVED_FROM_DRONE:
            self.color = constants.BLUE # Mensagem recebida de drone
            self.size = constants.SIZE_WHEN_RECEIVING_MESSAGE
        if self.receivedFromLastTimerTick == constants.MESSAGE_RECEIVED_FROM_TOWER:
            self.color = constants.RED # Vermelho, mensagem da torre
            self.size = constants.SIZE_WHEN_RECEIVING_MESSAGE
        self.visualization.paint_node(
                self.provider.get_id(),
                self.color
            )
        self.visualization.resize_nodes(self.size)
        self.receivedFromLastTimerTick = constants.NO_MESSAGE_RECEIVED
        self.scheduleAppearanceTimer()