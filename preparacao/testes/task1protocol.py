from gradysim.protocol.interface import IProtocol
from gradysim.simulator.extension.visualization_controller import VisualizationController
from gradysim.protocol.messages.mobility import GotoCoordsMobilityCommand
import random

class Task1Protocol (IProtocol):

    def initialize(self) -> None:
        self.visualization = VisualizationController(self)

        self.provider.schedule_timer(
            "appearance",
            self.provider.current_time() + 0.5
        )
        self.provider.schedule_timer(
            "mobility",  # We don't care about the name since we're only going to use one
            self.provider.current_time() + 5  # Scheduling it 5 second from now
        )
    
    def handle_packet(self, message):
        pass
    
    def handle_telemetry(self, telemetry):
        pass
    
    def handle_timer(self, timer):
        if timer == "appearance":
            self.visualization.paint_node(
                self.provider.get_id(),
                (0, 0, 0) # RGB preto
            )
            self.visualization.resize_nodes(1.5)
        else: # timer == "mobility"
            command = GotoCoordsMobilityCommand(
                random.uniform(-50, 50),
                random.uniform(-50, 50),
                random.uniform(0, 50)
            )
            self.provider.send_mobility_command(command)
            # Scheduling a new timer
            self.provider.schedule_timer(
                "mobility",
                self.provider.current_time() + 5
            )

    
    def finish(self):
        pass