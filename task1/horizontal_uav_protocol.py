from gradysim.protocol.messages.mobility import GotoCoordsMobilityCommand
import random
from uav_protocol import UAVProtocol

class HorizontalUAVProtocol (UAVProtocol):

    def move(self):
        if self.current_position is not None:
            x, y, z = self.current_position
        command = GotoCoordsMobilityCommand(random.uniform(-50, 50), y, 0)
        self.provider.send_mobility_command(command)
        super().scheduleMobilityTimer()