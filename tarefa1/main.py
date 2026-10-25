import logging

from gradysim.simulator.simulation import SimulationBuilder, SimulationConfiguration
from gradysim.simulator.handler.timer import TimerHandler
from gradysim.simulator.handler.mobility import MobilityHandler, MobilityConfiguration
from gradysim.simulator.handler.communication import CommunicationHandler, CommunicationMedium
from message_transmitter_uav_protocol import MessageTransmitterUAVProtocol
from communicable_uav_protocol import CommunicableUAVProtocol
from flight_plan import FlightPlan
from real_time_handler import RealTimeHandler, PacedVisualizationHandler
from simulation_metrics import MetricsHandler
import constants

'''
Cria 'DRONE_COUNT' drones em rotação ao redor do centro fixo (0, 0, 0).
'''
def main():
    if constants.SIMULATION_MODE not in (constants.TOPOLOGY, constants.RANDOM):
        raise ValueError('SIMULATION_MODE deve ser TOPOLOGY ou RANDOM.')
    logger = logging.getLogger()
    logger.setLevel(constants.LOG_LEVEL)
    flight_plan = FlightPlan(
        constants.EXTERNAL_CORE_TARGETS, constants.DRONE_COUNT
    )
    config = SimulationConfiguration(
        # O handler abaixo controla o ritmo, evitando as esperas relativas do simulador.
        duration=constants.SIMULATION_DURATION, real_time=False,
        # Desativar execution_logging suprime também INFO durante a simulação.
        debug=logger.isEnabledFor(logging.DEBUG), execution_logging=True
    )
    builder = SimulationBuilder(config)
    center = flight_plan.get_position(0)
    for index in range(constants.DRONE_COUNT):
        angle = index * 360 / constants.DRONE_COUNT
        builder.add_node(
            MessageTransmitterUAVProtocol,
            FlightPlan.position_on_circle(center, constants.FORMATION_RADIUS, angle),
        )

    # Deslocamentos em relação ao centro inicial: leste, oeste, norte e sul.
    external_drones = (
        ((40, 0, 0), 0),
        ((-40, 0, 0), 1),
        ((0, 40, 0), 2),
        ((0, -40, 0), 3),
    )
    for offset, external_index in external_drones:
        position = tuple(c + d for c, d in zip(center, offset))
        builder.add_node(CommunicableUAVProtocol.with_external(external_index), position)

    builder.add_handler(TimerHandler())
    builder.add_handler(CommunicationHandler(CommunicationMedium(
        transmission_range=constants.RADIO_RANGE
    )))
    builder.add_handler(MobilityHandler(MobilityConfiguration(
        update_rate=constants.RANDOM_MOVEMENT_INTERVAL
    )) if constants.SIMULATION_MODE == constants.RANDOM else MobilityHandler())
    pacer = RealTimeHandler(constants.REAL_TIME)
    builder.add_handler(PacedVisualizationHandler(pacer))
    builder.add_handler(pacer)
    builder.add_handler(MetricsHandler())

    simulation = builder.build()
    # O builder redefine o nível para INFO/DEBUG; reaplica também WARNING e superiores.
    logger.setLevel(constants.LOG_LEVEL)
    simulation.start_simulation()

if __name__ == "__main__":
    main()
