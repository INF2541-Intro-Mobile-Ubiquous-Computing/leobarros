from gradysim.protocol.interface import IProtocol
from gradysim.simulator.extension.visualization_controller import VisualizationController
from gradysim.protocol.messages.communication import CommunicationCommand, CommunicationCommandType
import logging

class TowerProtocol (IProtocol):
    sent: int
    received: int

    def initialize(self) -> None:
        self.sent = 0
        self.received = 0

        self.visualization = VisualizationController(self)
        self.provider.schedule_timer(
            "appearance",
            self.provider.current_time() + 1
        )

        self.provider.schedule_timer(
            "communication",
            self.provider.current_time() + 1
        )
    
    def handle_packet(self, message):
        self.received += 1
        logging.info(f"Mensagem recebida num.{self.received}: {message}")
    
    def handle_telemetry(self, telemetry):
        pass
    
    def handle_timer(self, timer):
        if timer == "appearance":
            self.visualization.paint_node(
                self.provider.get_id(),
                (255, 0, 0) # RGB vermelho
            )
            self.visualization.resize_nodes(1.5)
        else: # timer == "communication"
            command = CommunicationCommand(
                CommunicationCommandType.BROADCAST,
                message="[TORRE] Quem vai ganhar a eleição para presidente?"
            )
            self.provider.send_communication_command(command)
            self.sent += 1
            # Scheduling a new timer
            self.provider.schedule_timer(
                "communication",
                self.provider.current_time() + 1
            )
    
    def finish(self):
        logging.info(f"Mensagens: "
            f"Enviadas={self.sent} ; Recebidas={self.received}")