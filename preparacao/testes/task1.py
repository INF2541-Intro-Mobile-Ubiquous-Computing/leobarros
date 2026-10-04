import logging
from gradysim.simulator.simulation import SimulationBuilder, SimulationConfiguration
from task1protocol import Task1Protocol
from gradysim.simulator.handler.timer import TimerHandler
from gradysim.simulator.handler.communication import CommunicationHandler
from gradysim.simulator.handler.mobility import MobilityHandler
from gradysim.simulator.handler.visualization import VisualizationHandler

#logging.basicConfig(level=logging.INFO)

def main():
    print("Setup")
    config = SimulationConfiguration(
        duration=5,
        real_time=True
    )
    builder = SimulationBuilder(config)
    builder.add_node(Task1Protocol, (0, 0, 0))
    builder.add_node(Task1Protocol, (50, 0, 0))
    builder.add_node(Task1Protocol, (-50, 0, 0))

    builder.add_handler(TimerHandler())
    builder.add_handler(CommunicationHandler())
    builder.add_handler(MobilityHandler())
    builder.add_handler(VisualizationHandler())

    simulation = builder.build()
    simulation.start_simulation()

if __name__ == "__main__":
    main()