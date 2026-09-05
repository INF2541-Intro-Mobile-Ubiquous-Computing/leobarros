from gradysim.protocol.messages.mobility import GotoCoordsMobilityCommand
from gradysim.protocol.messages.communication import CommunicationCommand, CommunicationCommandType
from uav_protocol import UAVProtocol
import random

class VerticalUAVProtocol (UAVProtocol):

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

    def forwardMessage(self, message):
        command = CommunicationCommand(
            CommunicationCommandType.BROADCAST,
            message=f"Vertical {self.provider.get_id()}: {message}"
        )
        self.provider.send_communication_command(command)
        self.sent += 1

    def move(self):
        if self.current_position is not None:
            x, y, z = self.current_position
        command = GotoCoordsMobilityCommand(x, random.uniform(-20, 20), 0)
        self.provider.send_mobility_command(command)
        super().scheduleMobilityTimer()