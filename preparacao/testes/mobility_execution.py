from mobility_protocol import MobilityProtocol
from gradysim.simulator.handler.communication import CommunicationMedium, CommunicationHandler
from gradysim.simulator.handler.mobility import MobilityHandler
from gradysim.simulator.handler.timer import TimerHandler
from gradysim.simulator.simulation import SimulationBuilder, SimulationConfiguration
from gradysim.simulator.handler.visualization import VisualizationHandler


def main():
    config = SimulationConfiguration(
        duration=1000
    )
    builder = SimulationBuilder(config)

    # Adding 10 nodes on (0, 0, 0)
    for _ in range(10):
        builder.add_node(MobilityProtocol, (0, 0, 0))

    builder.add_handler(TimerHandler())

    # We will limit the communication range.
    # This will help us see the effect of mobility on
    # the nodes' position.
    medium = CommunicationMedium(
        transmission_range=30
    )

    builder.add_handler(CommunicationHandler(medium))

    # Adding mobility handler
    builder.add_handler(MobilityHandler())

    # Adding visualization handler to the simulator
    builder.add_handler(VisualizationHandler())

    simulation = builder.build()
    simulation.start_simulation()


if __name__ == "__main__":
    main()
