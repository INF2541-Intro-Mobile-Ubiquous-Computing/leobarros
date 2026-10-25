import math
import unittest
from unittest.mock import Mock, patch

from gradysim.simulator.handler.mobility import MobilityHandler
from gradysim.simulator.handler.timer import TimerHandler
from gradysim.simulator.simulation import SimulationBuilder, SimulationConfiguration

import constants
from flight_plan import FlightPlan
from movable_core_uav_protocol import MovableCoreUAVProtocol


class FormationTest(unittest.TestCase):
    def setUp(self):
        mode = patch.object(constants, 'SIMULATION_MODE', constants.TOPOLOGY)
        mode.start()
        self.addCleanup(mode.stop)

    def test_center_stays_at_origin(self):
        plan = FlightPlan()
        for time in (0, 0.1, 5, 50, 1000):
            with self.subTest(time=time):
                self.assertEqual(plan.get_position(time), (0, 0, 0))

    def test_angular_speed_preserves_tangential_speed(self):
        self.assertAlmostEqual(
            math.radians(constants.ANGULAR_SPEED) * constants.FORMATION_RADIUS,
            constants.ROTATION_SPEED,
        )

    def test_independent_plans_and_movement_over_a_complete_cycle(self):
        cycle_duration = 360 / abs(constants.ANGULAR_SPEED)
        builder = SimulationBuilder(SimulationConfiguration(duration=cycle_duration + 1))
        mobility = MobilityHandler()
        timer = TimerHandler()
        builder.add_handler(timer)
        builder.add_handler(mobility)
        for index in range(constants.DRONE_COUNT):
            builder.add_node(MovableCoreUAVProtocol, FlightPlan.position_on_circle(
                (0, 0, 0), constants.FORMATION_RADIUS,
                index * 360 / constants.DRONE_COUNT,
            ))
        simulation = builder.build()
        samples = []
        plans = {}
        original_move = MovableCoreUAVProtocol.move

        def observe_move(drone):
            original_move(drone)
            time = drone.provider.current_time()
            plans[drone.provider.get_id()] = drone.flight_plan
            samples.append((time, drone.center, drone.target_position, drone.initial_angle))

        with patch.object(MovableCoreUAVProtocol, 'move', observe_move):
            simulation.start_simulation()

        self.assertEqual(len(plans), 9)
        self.assertEqual(len({id(plan) for plan in plans.values()}), 9)
        for time, center, target, initial_angle in samples:
            self.assertEqual(center, (0, 0, 0))
            angle = math.degrees(math.atan2(target[1] - center[1], target[0] - center[0]))
            expected_angle = initial_angle + constants.ANGULAR_SPEED * time
            self.assertAlmostEqual((angle - expected_angle + 180) % 360 - 180, 0)
            self.assertAlmostEqual(math.dist(target, center), constants.FORMATION_RADIUS)
        for time in range(0, int(cycle_duration) + 1, 5):
            self.assertEqual(sum(math.isclose(t, time, abs_tol=1e-8) for t, *_ in samples), 9)

        # Verifica o centro físico e a formação ao final de uma volta.
        positions = [node.position for node in mobility.nodes.values()]
        center = tuple(sum(p[axis] for p in positions) / len(positions) for axis in range(3))
        self.assertLess(math.dist(center, (0, 0, 0)), 1e-8)
        for position in positions:
            self.assertAlmostEqual(math.dist(position, center), constants.FORMATION_RADIUS, delta=0.2)

    def test_node_really_moves_using_simulation_time(self):
        builder = SimulationBuilder(SimulationConfiguration(duration=5.5))
        mobility = MobilityHandler()
        builder.add_handler(TimerHandler())
        builder.add_handler(mobility)
        builder.add_node(MovableCoreUAVProtocol, (constants.FORMATION_RADIUS, 0, 0))
        builder.build().start_simulation()
        position = mobility.nodes[0].position
        plan = FlightPlan()
        expected = FlightPlan.position_on_circle(
            plan.get_position(5.5), constants.FORMATION_RADIUS, constants.ANGULAR_SPEED * 5.5
        )
        target_speed = abs(constants.ROTATION_SPEED)
        self.assertGreaterEqual(constants.MOVEMENT_SPEED, target_speed)
        tolerance = target_speed * constants.MOVEMENT_INTERVAL + constants.MOVEMENT_SPEED * 0.02
        self.assertLessEqual(math.dist(position, expected), tolerance)

    def test_rotation_uses_absolute_time_and_supports_both_directions(self):
        drone = MovableCoreUAVProtocol()
        drone.provider = Mock()
        drone.flight_plan = FlightPlan()
        drone.initial_angle = 0
        for speed, time, direction in (
            (9, 40, (1, 0)), (9, 10, (0, 1)),
            (-9, 10, (0, -1)), (0, 27, (1, 0)), (9, 0, (1, 0)),
        ):
            with self.subTest(speed=speed, time=time), patch.object(constants, 'ANGULAR_SPEED', speed):
                drone.provider.current_time.return_value = time
                drone.move()
                center = drone.flight_plan.get_position(time)
                for axis in (0, 1):
                    self.assertAlmostEqual(
                        drone.target_position[axis],
                        center[axis] + constants.FORMATION_RADIUS * direction[axis],
                    )
                self.assertEqual(drone.target_position[2], center[2])
                command = drone.provider.send_mobility_command.call_args.args[0]
                self.assertEqual((command.param_1, command.param_2, command.param_3), drone.target_position)


if __name__ == '__main__':
    unittest.main()
