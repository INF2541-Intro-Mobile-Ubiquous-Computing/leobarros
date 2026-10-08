from gradysim.simulator.simulation import SimulationBuilder, SimulationConfiguration
from gradysim.simulator.handler.timer import TimerHandler
from gradysim.simulator.handler.visualization import VisualizationHandler
from gradysim.simulator.handler.mobility import MobilityHandler
from movable_node_protocol import MovableNodeProtocol
from flight_plan import FlightPlan
import constants

'''
Cria 'DRONE_COUNT' drones em formação de círculo e atribui a eles um plano de vôo.
'''
def main():
    flight_plan = FlightPlan(
        list(constants.FLIGHT_PLAN_POINTS), constants.SEGMENT_DURATION
    )
    config = SimulationConfiguration( duration=flight_plan.cycle_duration * 5 )
    builder = SimulationBuilder(config)
    center = flight_plan.get_position(0)
    for index in range(constants.DRONE_COUNT):
        angle = index * 360 / constants.DRONE_COUNT
        builder.add_node(
            MovableNodeProtocol,
            FlightPlan.position_on_circle(center, constants.FORMATION_RADIUS, angle),
        )

    builder.add_handler(TimerHandler())
    builder.add_handler(MobilityHandler())
    builder.add_handler(VisualizationHandler())

    simulation = builder.build()
    simulation.start_simulation()

if __name__ == "__main__":
    main()
