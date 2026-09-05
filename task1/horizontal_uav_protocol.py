from gradysim.protocol.interface import IProtocol
from gradysim.simulator.extension.visualization_controller import VisualizationController
from gradysim.protocol.messages.mobility import GotoCoordsMobilityCommand
import random
from typing import Optional
from gradysim.protocol.position import Position
from gradysim.protocol.messages.communication import CommunicationCommand, CommunicationCommandType
import logging


class HorizontalUAVProtocol (IProtocol):
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
        
        self.current_position: Optional[Position] = None
        self.provider.schedule_timer(
            "mobility",  # We don't care about the name since we're only going to use one
            self.provider.current_time() + 1  # Scheduling it 5 second from now
        )
    
    def handle_packet(self, message):
        self.received += 1
        if "[PERGUNTA]" in message:
            #logging.info(f"Mensagem recebida num.{self.received}: {message}")
            self.receivedFromLastCycle = 1
            command = CommunicationCommand(
                CommunicationCommandType.BROADCAST,
                message=f"Horizontal {self.provider.get_id()}: [RESPOSTA] E eu sei lá, ué"
            )
            self.provider.send_communication_command(command)
            self.sent += 1
        else:
            self.receivedFromLastCycle = 2
        command = CommunicationCommand(
            CommunicationCommandType.BROADCAST,
            message=f"Horizontal {self.provider.get_id()}: {message}"
        )
    
    def handle_telemetry(self, telemetry):
        self.current_position = telemetry.current_position
    
    def handle_timer(self, timer):
        if timer == "appearance":
            #logging.debug(f"Mensagem recebida no último ciclo: {self.receivedFromLastCycle}")
            color = (0, 0, 0) # Preto, drone
            # if self.receivedFromLastCycle == 2:
                # color = (0, 0, 255) # Azul, mensagem de drone
            if self.receivedFromLastCycle == 1:
                color = (255, 0, 0) # Vermelho, mensagem da torre
            self.visualization.paint_node(
                self.provider.get_id(),
                color
            )
            self.receivedFromLastCycle = 0
            self.visualization.resize_nodes(1.5)
            self.provider.schedule_timer(
                "appearance",
                self.provider.current_time() + 1
            )
        else: # timer == "mobility"
            if self.current_position is not None:
                x, y, z = self.current_position
            command = GotoCoordsMobilityCommand(
                random.uniform(-50, 50),
                y,
                0
            )
            self.provider.send_mobility_command(command)
            # Scheduling a new timer
            self.provider.schedule_timer(
                "mobility",
                self.provider.current_time() + 5
            )

    
    def finish(self):
        logging.info(f"Mensagens: "
            f"Enviadas={self.sent} ; Recebidas={self.received}")