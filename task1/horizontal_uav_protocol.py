from gradysim.protocol.interface import IProtocol
from gradysim.simulator.extension.visualization_controller import VisualizationController
from gradysim.protocol.messages.mobility import GotoCoordsMobilityCommand
import random
from typing import Optional
from gradysim.protocol.position import Position
from gradysim.protocol.messages.communication import CommunicationCommand, CommunicationCommandType
import logging
import constants

class HorizontalUAVProtocol (IProtocol):
    sent: int
    received: int
    receivedFromLastCycle: int

    # Inicialização
    def initialize(self) -> None:
        self.sent = 0
        self.received = 0
        self.receivedFromLastCycle = constants.NO_MESSAGE_RECEIVED
        self.initializeAppearanceTimer()
        self.initializeMobilityTimer()

    # Recebimento de mensagens
    def handle_packet(self, message):
        self.received += 1
        if "[PERGUNTA]" in message:
            self.sendAnswer()
        else:
            self.receivedFromLastCycle = constants.MESSAGE_RECEIVED_FROM_DRONE
        self.forwardMessage(message)

    # Recebimento de telemetria
    def handle_telemetry(self, telemetry):
        self.current_position = telemetry.current_position

    # Tick dos relógios
    def handle_timer(self, timer):
        if timer == "appearance":
            self.setColorAndSize()
        else: # timer == "mobility"
            self.moveRandomlyHorizontally()

    # Finalização do objeto
    def finish(self):
        logging.info(f"Mensagens: "
            f"Enviadas={self.sent} ; Recebidas={self.received}")

    def moveRandomlyHorizontally(self):
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

    def setColorAndSize(self):
        #logging.debug(f"Mensagem recebida no último ciclo: {self.receivedFromLastCycle}")
        color = constants.BLACK # Cor default do drone
            # if self.receivedFromLastCycle == 2:
                # color = constants.BLUE # Mensagem recebida de outro drone
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

    def initializeMobilityTimer(self):
        self.current_position: Optional[Position] = None
        self.provider.schedule_timer(
            "mobility",  # We don't care about the name since we're only going to use one
            self.provider.current_time() + 1  # Scheduling it 5 second from now
        )

    def initializeAppearanceTimer(self):
        self.visualization = VisualizationController(self)
        self.provider.schedule_timer(
            "appearance",
            self.provider.current_time() + 1
        )

    def forwardMessage(self, message):
        command = CommunicationCommand(
            CommunicationCommandType.BROADCAST,
            message=f"Horizontal {self.provider.get_id()}: {message}"
        )

    def sendAnswer(self):
        #logging.info(f"Mensagem recebida num.{self.received}: {message}")
        self.receivedFromLastCycle = 1
        command = CommunicationCommand(
                CommunicationCommandType.BROADCAST,
                message=f"Horizontal {self.provider.get_id()}: [RESPOSTA] E eu sei lá, ué"
            )
        self.provider.send_communication_command(command)
        self.sent += 1