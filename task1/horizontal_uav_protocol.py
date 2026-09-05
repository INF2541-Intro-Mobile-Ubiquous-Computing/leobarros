from gradysim.protocol.messages.mobility import GotoCoordsMobilityCommand
import random
from typing import Optional
from gradysim.protocol.position import Position
from gradysim.protocol.messages.communication import CommunicationCommand, CommunicationCommandType
from visible_node_protocol import VisibleNodeProtocol
import constants, shared

class HorizontalUAVProtocol (VisibleNodeProtocol):

    # Inicialização
    def initialize(self) -> None:
        super().initialize()
        self.current_position: Optional[Position] = None
        shared.scheduleMobilityTimer(self)

    # Recebimento de mensagens
    def handle_packet(self, message):
        self.received += 1
        if "[PERGUNTA]" in message:
            self.sendAnswer()
        else:
            self.receivedFromLastTimerTick = constants.MESSAGE_RECEIVED_FROM_DRONE
        self.forwardMessage(message)

    # Recebimento de telemetria
    def handle_telemetry(self, telemetry):
        self.current_position = telemetry.current_position

    # Tick dos relógios
    def handle_timer(self, timer):
        if timer == "appearance":
            self.setColorAndSize()
        elif timer == "mobility":
            self.moveRandomlyHorizontally()

    def moveRandomlyHorizontally(self):
        if self.current_position is not None:
            x, y, z = self.current_position
        command = GotoCoordsMobilityCommand(
                random.uniform(-50, 50),
                y,
                0
            )
        self.provider.send_mobility_command(command)
        shared.scheduleMobilityTimer(self)

    def setColorAndSize(self):
        #logging.debug(f"Mensagem recebida no último ciclo: {self.receivedFromLastCycle}")
        color = constants.BLACK # Cor default do drone
             #if self.receivedFromLastCycle == constants.MESSAGE_RECEIVED_FROM_DRONE:
                # color = constants.BLUE # Mensagem recebida de outro drone
        if self.receivedFromLastTimerTick == constants.MESSAGE_RECEIVED_FROM_TOWER:
            color = constants.RED # Vermelho, mensagem da torre
        self.visualization.paint_node(
                self.provider.get_id(),
                color
            )
        self.receivedFromLastTimerTick = constants.NO_MESSAGE_RECEIVED
        self.visualization.resize_nodes(1.5)
        super().scheduleAppearanceTimer()

    def forwardMessage(self, message):
        command = CommunicationCommand(
            CommunicationCommandType.BROADCAST,
            message=f"Horizontal {self.provider.get_id()}: {message}"
        )
        self.provider.send_communication_command(command)
        self.sent += 1

    def sendAnswer(self):
        #logging.info(f"Mensagem recebida num.{self.received}: {message}")
        self.receivedFromLastTimerTick = 1
        command = CommunicationCommand(
                CommunicationCommandType.BROADCAST,
                message=f"Horizontal {self.provider.get_id()}: [RESPOSTA] E eu sei lá, ué"
            )
        self.provider.send_communication_command(command)
        self.sent += 1