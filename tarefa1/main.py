from gradysim.simulator.simulation import SimulationBuilder, SimulationConfiguration
from gradysim.simulator.handler.timer import TimerHandler
from gradysim.simulator.handler.mobility import MobilityHandler
from gradysim.simulator.handler.communication import CommunicationHandler, CommunicationMedium
from movable_core_uav_protocol import MovableCoreUAVProtocol
from communicable_uav_protocol import CommunicableUAVProtocol
from flight_plan import FlightPlan
from real_time_handler import RealTimeHandler, PacedVisualizationHandler
import constants

'''
Cria 'DRONE_COUNT' drones em formação de círculo e atribui a eles um plano de vôo.
'''
def main():
    flight_plan = FlightPlan(
        list(constants.FLIGHT_PLAN_POINTS), constants.CENTER_SPEED
    )
    config = SimulationConfiguration(
        # O handler abaixo controla o ritmo, evitando as esperas relativas do simulador.
        duration=flight_plan.cycle_duration * 4, real_time=False
    )
    builder = SimulationBuilder(config)
    center = flight_plan.get_position(0)
    for index in range(constants.DRONE_COUNT):
        angle = index * 360 / constants.DRONE_COUNT
        builder.add_node(
            MovableCoreUAVProtocol,
            FlightPlan.position_on_circle(center, constants.FORMATION_RADIUS, angle),
        )

    # Deslocamentos em relação ao centro inicial: leste, oeste, norte e sul.
    external_drones = (
        ((30, 0, 0), 0),
        ((-30, 0, 0), 2),
        ((0, 30, 0), 4),
        ((0, -30, 0), 6),
    )
    for offset, target_index in external_drones:
        position = tuple(c + d for c, d in zip(center, offset))
        builder.add_node(CommunicableUAVProtocol.with_target(target_index), position)

    builder.add_handler(TimerHandler())
    builder.add_handler(CommunicationHandler(CommunicationMedium(
        transmission_range=constants.EXTERNAL_CONTACT_DISTANCE
    )))
    builder.add_handler(MobilityHandler())
    pacer = RealTimeHandler(constants.REAL_TIME)
    builder.add_handler(PacedVisualizationHandler(pacer))
    builder.add_handler(pacer)

    simulation = builder.build()
    simulation.start_simulation()

if __name__ == "__main__":
    main()
