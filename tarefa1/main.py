from gradysim.simulator.simulation import SimulationBuilder, SimulationConfiguration
from gradysim.simulator.handler.timer import TimerHandler
from gradysim.simulator.handler.visualization import VisualizationHandler
from core_protocol import CoreProtocol

def main():
    config = SimulationConfiguration(
        duration=5,
        real_time=5.0
    )
    builder = SimulationBuilder(config)
    builder.add_node(CoreProtocol, (0, 0, 0))

    builder.add_handler(TimerHandler())
    builder.add_handler(VisualizationHandler())

    simulation = builder.build()
    simulation.start_simulation()

if __name__ == "__main__":
    main()