import math
import random
import unittest
from unittest.mock import Mock, patch

from gradysim.simulator.handler.mobility import MobilityHandler, MobilityConfiguration
from gradysim.simulator.handler.timer import TimerHandler
from gradysim.simulator.simulation import SimulationBuilder, SimulationConfiguration

import constants
from flight_plan import FlightPlan
from movable_core_uav_protocol import MovableCoreUAVProtocol
from random_core_motion import RandomCoreMotion


class RandomCoreTest(unittest.TestCase):
    def test_direction_changes_each_second(self):
        rng = Mock()
        rng.uniform.side_effect = [0, math.pi / 2, math.pi]
        motion = RandomCoreMotion(10, 1, 1, 0, rng)
        self.assertEqual(motion.position, (10, 0))
        motion.position_at(0.9)
        self.assertEqual(rng.uniform.call_count, 1)
        motion.position_at(1)
        self.assertEqual(rng.uniform.call_count, 2)
        x, y = motion.position_at(1.5)
        self.assertAlmostEqual(x, 9)
        self.assertAlmostEqual(y, 0.5)
        motion.position_at(2)
        self.assertEqual(rng.uniform.call_count, 3)

    def test_boundary_triggers_inward_turn_before_next_second(self):
        rng = Mock()
        rng.uniform.return_value = 0
        motion = RandomCoreMotion(1, 4, 1, 0, rng)
        x, y = motion.position_at(0.5)
        self.assertAlmostEqual(x, -1)
        self.assertAlmostEqual(y, 0)
        self.assertEqual(rng.uniform.call_count, 2)
        x, y = motion.position_at(0.75)
        self.assertAlmostEqual(x, 0)
        self.assertAlmostEqual(y, 0)

    def test_late_updates_preserve_path_and_containment(self):
        coarse = RandomCoreMotion(10, 6, 1, 40, random.Random(19))
        fine = RandomCoreMotion(10, 6, 1, 40, random.Random(19))
        for step in range(1, 1001):
            position = fine.position_at(step / 100)
            self.assertLessEqual(math.hypot(*position), 10 + 1e-9)
        self.assertLess(math.dist(coarse.position_at(10), fine.position), 1e-8)
        with self.assertRaises(ValueError):
            fine.position_at(9)

    def test_actual_nodes_stay_in_moving_circle_through_plan_corners(self):
        for seed in (7, 19):
            with self.subTest(seed=seed), patch.object(constants, 'SIMULATION_MODE', constants.RANDOM):
                rng = random.Random(seed)
                builder = SimulationBuilder(SimulationConfiguration(duration=120, execution_logging=False))
                builder.add_handler(TimerHandler())
                builder.add_handler(MobilityHandler(MobilityConfiguration(
                    update_rate=constants.RANDOM_MOVEMENT_INTERVAL)))
                samples = []

                class ObservedCore(MovableCoreUAVProtocol):
                    def handle_telemetry(node, telemetry):
                        now = node.provider.current_time()
                        radius = math.dist(telemetry.current_position, node.flight_plan.get_position(now))
                        samples.append((node.provider.get_id(), radius))
                        super().handle_telemetry(telemetry)

                for index in range(constants.DRONE_COUNT):
                    builder.add_node(ObservedCore, FlightPlan.position_on_circle(
                        (0, 0, 0), constants.FORMATION_RADIUS,
                        index * 360 / constants.DRONE_COUNT))
                with patch('random_core_motion.random.uniform', side_effect=rng.uniform):
                    simulation = builder.build()
                    simulation.start_simulation()
                self.assertTrue(samples)
                self.assertLessEqual(max(radius for _, radius in samples), constants.FORMATION_RADIUS + 1e-7)
                self.assertEqual({index for index, radius in samples if radius < constants.FORMATION_RADIUS / 2},
                                 set(range(constants.DRONE_COUNT)))


if __name__ == '__main__':
    unittest.main()
