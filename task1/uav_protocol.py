from node_protocol import NodeProtocol
import constants
from typing import Optional
from gradysim.protocol.position import Position

class UAVProtocol (NodeProtocol):

    # Inicialização
    def initialize(self) -> None:
        super().initialize()
        self.color = constants.BLACK # Cor default do drone
        self.current_position: Optional[Position] = None
        self.scheduleMobilityTimer()

   # Recebimento de telemetria
    def handle_telemetry(self, telemetry):
        self.current_position = telemetry.current_position

    # Tick dos relógios
    def handle_timer(self, timer):
        super().handle_timer(timer)
        if timer == "mobility":
            self.move()

    def scheduleMobilityTimer(self):
        self.provider.schedule_timer(
            "mobility",
            self.provider.current_time() + constants.MOBILITY_INTERVAL
        )

    def move(self):
        pass