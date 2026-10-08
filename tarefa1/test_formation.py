import math
import unittest
from unittest.mock import patch

from gradysim.simulator.handler.mobility import MobilityHandler
from gradysim.simulator.handler.timer import TimerHandler
from gradysim.simulator.simulation import SimulationBuilder, SimulationConfiguration

import constants
from flight_plan import FlightPlan
from movable_node_protocol import MovableNodeProtocol


class FormationTest(unittest.TestCase):
    def test_independent_plans_and_movement_over_a_complete_cycle(self):
        builder = SimulationBuilder(SimulationConfiguration(duration=41))
        mobility = MobilityHandler()
        timer = TimerHandler()
        builder.add_handler(timer)
        builder.add_handler(mobility)
        for index in range(constants.DRONE_COUNT):
            builder.add_node(MovableNodeProtocol, FlightPlan.position_on_circle(
                constants.FLIGHT_PLAN_POINTS[0], constants.FORMATION_RADIUS,
                index * 360 / constants.DRONE_COUNT,
            ))
        simulation = builder.build()
        samples = []
        plans = {}
        original_move = MovableNodeProtocol.move

        def observe_move(drone):
            original_move(drone)
            time = drone.provider.current_time()
            plans[drone.provider.get_id()] = drone.flight_plan
            samples.append((time, drone.center, drone.target_position, drone.offset))

        with patch.object(MovableNodeProtocol, 'move', observe_move):
            simulation.start_simulation()

        self.assertEqual(len(plans), 9)
        self.assertEqual(len({id(plan) for plan in plans.values()}), 9)
        expected_plan = FlightPlan(list(constants.FLIGHT_PLAN_POINTS), constants.SEGMENT_DURATION)
        for time, center, target, offset in samples:
            self.assertEqual(center, expected_plan.get_position(time))
            self.assertEqual(target, tuple(c + d for c, d in zip(center, offset)))
            self.assertAlmostEqual(math.dist(target, center), constants.FORMATION_RADIUS)
        for time in (0, 5, 10, 15, 20, 25, 30, 35, 40):
            self.assertEqual(sum(t == time for t, *_ in samples), 9)

        # Todos realmente percorreram o trajeto: observar posições durante a execução
        # é verificado no teste abaixo; aqui verificamos a formação ao final.
        positions = [node.position for node in mobility.nodes.values()]
        center = tuple(sum(p[axis] for p in positions) / len(positions) for axis in range(3))
        for position in positions:
            self.assertAlmostEqual(math.dist(position, center), constants.FORMATION_RADIUS, places=6)

    def test_node_really_moves_using_simulation_time(self):
        builder = SimulationBuilder(SimulationConfiguration(duration=5.5))
        mobility = MobilityHandler()
        builder.add_handler(TimerHandler())
        builder.add_handler(mobility)
        builder.add_node(MovableNodeProtocol, (constants.FORMATION_RADIUS, 0, 0))
        builder.build().start_simulation()
        position = mobility.nodes[0].position
        # Atualização por segundo: em t=5.5, segue o alvo definido em t=5.
        self.assertAlmostEqual(position[0], constants.FORMATION_RADIUS + 45, delta=0.2)
        self.assertEqual(position[1:], (0, 0))


if __name__ == '__main__':
    unittest.main()
