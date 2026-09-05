from gradysim.protocol.messages.mobility import GotoCoordsMobilityCommand
from typing import Optional
from gradysim.protocol.position import Position
from gradysim.protocol.messages.communication import CommunicationCommand, CommunicationCommandType
from node_protocol import NodeProtocol
import random, logging, constants, shared

class VerticalUAVProtocol (NodeProtocol):

    def initialize(self) -> None:
        super().initialize()
        self.color = constants.BLACK # Cor default do drone
        # TODO self.current_position: Optional[Position] = None
        # shared.scheduleMobilityTimer(self)

    # Recebimento de mensagens
    def handle_packet(self, message):
        pass
        # TODO self.received += 1
        # if "[PERGUNTA]" in message:
        #     #logging.info(f"Mensagem recebida num.{self.received}: {message}")
        #     self.receivedFromLastTimerTick = constants.MESSAGE_RECEIVED_FROM_TOWER
        # else:
        #     self.receivedFromLastTimerTick = constants.MESSAGE_RECEIVED_FROM_DRONE
        #     #logging.info(f"Alterou {self.receivedFromLastTimerTick}")
        # self.forwardMessage(message)

    # Recebimento de telemetria
    def handle_telemetry(self, telemetry):
        self.current_position = telemetry.current_position

    # Tick dos relógios
    # def handle_timer(self, timer):
    #     if timer == "appearance":
    #         self.setColorAndSize()
        # TODO elif timer == "mobility":
        #     self.moveRandomlyVertically()

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
        shared.scheduleMobilityTimer(self)