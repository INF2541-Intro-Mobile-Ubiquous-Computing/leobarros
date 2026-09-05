from gradysim.protocol.messages.mobility import GotoCoordsMobilityCommand
import random
from gradysim.protocol.messages.communication import CommunicationCommand, CommunicationCommandType
from uav_protocol import UAVProtocol

class HorizontalUAVProtocol (UAVProtocol):

    def move(self):
        if self.current_position is not None:
            x, y, z = self.current_position
        command = GotoCoordsMobilityCommand(random.uniform(-50, 50), y, 0)
        self.provider.send_mobility_command(command)
        super().scheduleMobilityTimer()

    def forwardMessage(self, message):
        command = CommunicationCommand(
            CommunicationCommandType.BROADCAST,
            message=f"Horizontal {self.provider.get_id()}: {message}"
        )
        self.provider.send_communication_command(command)
        self.sent += 1