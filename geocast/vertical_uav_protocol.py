from gradysim.protocol.messages.mobility import GotoCoordsMobilityCommand
from gradysim.protocol.messages.communication import CommunicationCommand, CommunicationCommandType
from uav_protocol import UAVProtocol
import random

class VerticalUAVProtocol (UAVProtocol):

    def move(self):
        if self.current_position is not None:
            x, y, z = self.current_position
        command = GotoCoordsMobilityCommand(x, random.uniform(-20, 20), 0)
        self.provider.send_mobility_command(command)
        super().scheduleMobilityTimer()