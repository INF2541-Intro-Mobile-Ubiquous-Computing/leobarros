from gradysim.protocol.interface import IProtocol
from gradysim.simulator.extension.visualization_controller import VisualizationController
from gradysim.protocol.messages.communication import CommunicationCommand, CommunicationCommandType
import logging

class TowerProtocol (IProtocol):
    sent: int
    received: int
    receivedFromLastCycle: int

    def initialize(self) -> None:
        self.sent = 0
        self.received = 0
        self.receivedFromLastCycle = 0 # 0: sem mensagem; 1: torre; 2: drone

        self.visualization = VisualizationController(self)
        self.provider.schedule_timer(
            "appearance",
            self.provider.current_time() + 1
        )

        self.provider.schedule_timer(
            "communication",
            self.provider.current_time() + 3
        )
    
    def handle_packet(self, message):
        self.received += 1
        self.receivedFromLastCycle = 2 # Obrigatoriamente a torre recebeu de um drone
        # logging.info(f"Mensagem recebida num.{self.received}: {message}")
    
    def handle_telemetry(self, telemetry):
        pass
    
    def handle_timer(self, timer):
        if timer == "appearance":
            color = (255, 0, 0) # Vermelho, cor da torre
            if self.receivedFromLastCycle > 0:
                color = (0, 0, 255) # Azul, mensagem de drone
                self.receivedFromLastCycle = 0
            self.visualization.paint_node(
                self.provider.get_id(),
                color
            )
            self.visualization.resize_nodes(1.5)
            self.provider.schedule_timer(
                "appearance",
                self.provider.current_time() + 1
            )
        else: # timer == "communication"
            command = CommunicationCommand(
                CommunicationCommandType.BROADCAST,
                message="[PERGUNTA] Quem vai ganhar a eleição para presidente?"
            )
            self.provider.send_communication_command(command)
            self.sent += 1
            #logging.info("Torre envia mensagem")
            # Scheduling a new timer
            self.provider.schedule_timer(
                "communication",
                self.provider.current_time() + 3
            )
    
    def finish(self):
        logging.info(f"Mensagens: "
            f"Enviadas={self.sent} ; Recebidas={self.received}")