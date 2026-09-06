from gradysim.simulator.simulation import SimulationBuilder, SimulationConfiguration
from tower_protocol import TowerProtocol
from horizontal_uav_protocol import HorizontalUAVProtocol
from vertical_uav_protocol import VerticalUAVProtocol
from gradysim.simulator.handler.timer import TimerHandler
from gradysim.simulator.handler.communication import CommunicationHandler, CommunicationMedium
from gradysim.simulator.handler.mobility import MobilityHandler
from gradysim.simulator.handler.visualization import VisualizationHandler
from final_uav_protocol import FinalUAVProtocol

def main():
    config = SimulationConfiguration(
        duration=20,
        real_time=5.0
    )
    builder = SimulationBuilder(config)
    builder.add_node(TowerProtocol, (0, -50, 0))
    
    builder.add_node(HorizontalUAVProtocol, (30, -20, 0))
    builder.add_node(HorizontalUAVProtocol, (-30, -20, 0))

    builder.add_node(VerticalUAVProtocol, (-30, 10, 0))
    builder.add_node(VerticalUAVProtocol, (30, 10, 0))

    builder.add_node(FinalUAVProtocol, (50, 40, 0))
    builder.add_node(FinalUAVProtocol, (-50, 40, 0))

    medium = CommunicationMedium(
        transmission_range=60,
        delay=0.1,
        failure_rate=0.1
    )
    builder.add_handler(CommunicationHandler(medium))

    builder.add_handler(TimerHandler())
    builder.add_handler(MobilityHandler())
    builder.add_handler(VisualizationHandler())

    simulation = builder.build()
    simulation.start_simulation()

if __name__ == "__main__":
    main()