from gradysim.protocol.interface import IProtocol
from gradysim.simulator.extension.visualization_controller import VisualizationController
import constants, shared, logging

class VisibleNodeProtocol (IProtocol):
    sent: int
    received: int
    receivedFromLastTimerTick: int

    def initialize(self):
        self.sent = 0
        self.received = 0
        self.receivedFromLastTimerTick = constants.NO_MESSAGE_RECEIVED 
        self.visualization = VisualizationController(self)
        shared.scheduleAppearanceTimer(self)

    # Recebimento de mensagens
    def handle_packet(self, message):
        pass
        
    # Recebimento de telemetria
    def handle_telemetry(self, telemetry):
        pass
    
    # Tick dos relógios
    def handle_timer(self, timer):
        pass
    
    # Finalização do objeto
    def finish(self):
        logging.info(f"Mensagens: "
            f"Enviadas={self.sent} ; Recebidas={self.received}")