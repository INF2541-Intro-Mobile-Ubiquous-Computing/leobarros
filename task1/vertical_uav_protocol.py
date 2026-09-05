from gradysim.protocol.interface import IProtocol
from gradysim.simulator.extension.visualization_controller import VisualizationController
from gradysim.protocol.messages.mobility import GotoCoordsMobilityCommand
from typing import Optional
from gradysim.protocol.position import Position
from gradysim.protocol.messages.communication import CommunicationCommand, CommunicationCommandType
import random, logging, constants

class VerticalUAVProtocol (IProtocol):
    sent: int
    received: int
    receivedFromLastCycle: int

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
            #logging.info(f"Mensagem recebida num.{self.received}: {message}")
            self.receivedFromLastCycle = constants.MESSAGE_RECEIVED_FROM_TOWER
        else:
            self.receivedFromLastCycle = constants.MESSAGE_RECEIVED_FROM_DRONE
            #logging.info(f"Alterou {self.receivedFromLastCycle}")
        self.forwardMessage(message)

    # Recebimento de telemetria
    def handle_telemetry(self, telemetry):
        self.current_position = telemetry.current_position

    # Tick dos relógios
    def handle_timer(self, timer):
        if timer == "appearance":
            self.setColorAndSize()
        else: # timer == "mobility"
            self.moveRandomlyVertically()

    # Finalização do objeto
    def finish(self):
        logging.info(f"Mensagens: "
            f"Enviadas={self.sent} ; Recebidas={self.received}")

    def forwardMessage(self, message):
        command = CommunicationCommand(
            CommunicationCommandType.BROADCAST,
            message=f"Vertical {self.provider.get_id()}: {message}"
        )
        self.provider.send_communication_command(command)
        self.sent += 1

    def moveRandomlyVertically(self):
        if self.current_position is not None:
            x, y, z = self.current_position
        command = GotoCoordsMobilityCommand(
                x,
                random.uniform(-20, 20),
                0
            )
        self.provider.send_mobility_command(command)
            # Scheduling a new timer
        self.provider.schedule_timer(
                "mobility",
                self.provider.current_time() + constants.MOVEMENT_INTERVAL
            )

    def setColorAndSize(self):
        color = constants.BLACK # Cor default do drone
            # if self.receivedFromLastCycle == constants.MESSAGE_RECEIVED_FROM_DRONE:
            #     color = constants.BLUE # Mensagem de drone
            #     self.receivedFromLastCycle = constants.NO_MESSAGE_RECEIVED
        logging.info(f"Recebido: {self.receivedFromLastCycle}")
        if self.receivedFromLastCycle == constants.MESSAGE_RECEIVED_FROM_TOWER:
            color = constants.RED # Mensagem da torre
        self.visualization.paint_node(
                self.provider.get_id(),
                color
            )
        self.visualization.resize_nodes(1.5)
        self.receivedFromLastCycle = constants.NO_MESSAGE_RECEIVED
        logging.info(f"Resetou {self.receivedFromLastCycle}")
        self.provider.schedule_timer(
                "appearance",
                self.provider.current_time() + constants.REDRAW_INTERVAL
            )
    
    def initializeMobilityTimer(self):
        self.current_position: Optional[Position] = None
        self.provider.schedule_timer(
            "mobility",  # We don't care about the name since we're only going to use one
            self.provider.current_time() + constants.MOVEMENT_INTERVAL  # Scheduling it 5 second from now
        )

    def initializeAppearanceTimer(self):
        self.visualization = VisualizationController(self)
        self.provider.schedule_timer(
            "appearance",
            self.provider.current_time() + constants.REDRAW_INTERVAL
        )