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
    def test_center_keeps_speed_on_unequal_segments_and_closes_cycle(self):
        points = ((-50, 50, 0), (-50, -50, 0), (50, 50, 0), (50, -50, 0))
        plan = FlightPlan(points, speed=3)
        self.assertAlmostEqual(plan.segment_durations[0], 100 / 3)
        self.assertAlmostEqual(plan.segment_durations[1], math.sqrt(20000) / 3)
        start_time = 0
        for index, duration in enumerate(plan.segment_durations):
            with self.subTest(segment=index):
                t = start_time + duration / 2
                self.assertAlmostEqual(math.dist(plan.get_position(t), plan.get_position(t + 0.1)), 0.3)
                expected = points[(index + 1) % len(points)]
                self.assertLess(math.dist(plan.get_position(start_time + duration), expected), 1e-10)
            start_time += duration
        self.assertEqual(plan.get_position(plan.cycle_duration), points[0])
        self.assertLess(math.dist(plan.get_position(plan.cycle_duration + 5), plan.get_position(5)), 1e-10)

    def test_repeated_points_and_invalid_plans(self):
        plan = FlightPlan(((0, 0, 0), (0, 0, 0), (3, 0, 0)), speed=3)
        self.assertEqual(plan.get_position(0), (0, 0, 0))
        self.assertEqual(plan.get_position(1), (3, 0, 0))
        for points, speed in (
            (((0, 0, 0), (3, 0, 0)), 0),
            (((0, 0, 0), (3, 0, 0)), -1),
            (((0, 0, 0),), 3),
            (((0, 0, 0), (0, 0, 0)), 3),
        ):
            with self.subTest(points=points, speed=speed), self.assertRaises(ValueError):
                FlightPlan(points, speed)

    def test_angular_speed_preserves_tangential_speed(self):
        self.assertAlmostEqual(
            math.radians(constants.ANGULAR_SPEED) * constants.FORMATION_RADIUS,
            constants.ROTATION_SPEED,
        )

    def test_independent_plans_and_movement_over_a_complete_cycle(self):
        cycle_duration = FlightPlan(constants.FLIGHT_PLAN_POINTS, constants.CENTER_SPEED).cycle_duration
        builder = SimulationBuilder(SimulationConfiguration(duration=cycle_duration + 1))
        mobility = MobilityHandler()
        timer = TimerHandler()
        builder.add_handler(timer)
        builder.add_handler(mobility)
        for index in range(constants.DRONE_COUNT):
            builder.add_node(MovableCoreUAVProtocol, FlightPlan.position_on_circle(
                constants.FLIGHT_PLAN_POINTS[0], constants.FORMATION_RADIUS,
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
        expected_plan = FlightPlan(list(constants.FLIGHT_PLAN_POINTS), constants.CENTER_SPEED)
        for time, center, target, initial_angle in samples:
            self.assertEqual(center, expected_plan.get_position(time))
            angle = math.degrees(math.atan2(target[1] - center[1], target[0] - center[0]))
            expected_angle = initial_angle + constants.ANGULAR_SPEED * time
            self.assertAlmostEqual((angle - expected_angle + 180) % 360 - 180, 0)
            self.assertAlmostEqual(math.dist(target, center), constants.FORMATION_RADIUS)
        for time in range(0, int(cycle_duration) + 1, 5):
            self.assertEqual(sum(math.isclose(t, time, abs_tol=1e-8) for t, *_ in samples), 9)

        # Todos realmente percorreram o trajeto: observar posições durante a execução
        # é verificado no teste abaixo; aqui verificamos a formação ao final.
        positions = [node.position for node in mobility.nodes.values()]
        center = tuple(sum(p[axis] for p in positions) / len(positions) for axis in range(3))
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
        plan = FlightPlan(list(constants.FLIGHT_PLAN_POINTS), constants.CENTER_SPEED)
        expected = FlightPlan.position_on_circle(
            plan.get_position(5.5), constants.FORMATION_RADIUS, constants.ANGULAR_SPEED * 5.5
        )
        center_speed = max(
            math.dist(point, plan.points[(index + 1) % len(plan.points)]) / plan.segment_durations[index]
            for index, point in enumerate(plan.points)
        )
        target_speed = center_speed + constants.FORMATION_RADIUS * abs(math.radians(constants.ANGULAR_SPEED))
        self.assertGreaterEqual(constants.MOVEMENT_SPEED, target_speed)
        tolerance = target_speed * constants.MOVEMENT_INTERVAL + constants.MOVEMENT_SPEED * 0.02
        self.assertLessEqual(math.dist(position, expected), tolerance)

    def test_rotation_uses_absolute_time_and_supports_both_directions(self):
        drone = MovableCoreUAVProtocol()
        drone.provider = Mock()
        drone.flight_plan = FlightPlan(list(constants.FLIGHT_PLAN_POINTS), constants.CENTER_SPEED)
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
