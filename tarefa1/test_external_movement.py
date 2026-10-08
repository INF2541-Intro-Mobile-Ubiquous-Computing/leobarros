import math
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from gradysim.simulator.simulation import SimulationBuilder, SimulationConfiguration
from gradysim.simulator.handler.timer import TimerHandler
from gradysim.simulator.handler.mobility import MobilityHandler
from flight_plan import FlightPlan
from movable_external_uav_protocol import MovableExternalUAVProtocol
from movable_core_uav_protocol import MovableCoreUAVProtocol
import constants


class ExternalMovementTest(unittest.TestCase):
    def make_drone(self):
        drone = MovableExternalUAVProtocol()
        drone.provider = Mock()
        drone.provider.current_time.return_value = 0
        with patch('movable_external_uav_protocol.VisibleNodeProtocol.initialize'):
            drone.initialize()
        return drone

    def test_initial_position_comes_from_telemetry_and_away_direction_is_fixed(self):
        drone = self.make_drone()
        self.assertIsNone(drone.current_position)
        with patch('movable_external_uav_protocol.random.uniform', return_value=0) as draw:
            drone.handle_telemetry(SimpleNamespace(current_position=(-30, 0, 0)))
            command = drone.provider.send_mobility_command.call_args.args[0]
            self.assertLess(command.param_1, -30)
            self.assertAlmostEqual(command.param_2, 0)
            count = drone.provider.send_mobility_command.call_count
            drone.provider.current_time.return_value = 1
            drone.handle_telemetry(SimpleNamespace(current_position=(-54, 0, 0)))
            drone.handle_timer(constants.MOVEMENT_TIMER)
            self.assertEqual(drone.provider.send_mobility_command.call_count, count)
            draw.assert_called_once()
        self.assertEqual(drone.away_until, constants.EXTERNAL_AWAY_DURATION)

    def test_interception_uses_future_target_and_contact_radius(self):
        drone = self.make_drone()
        drone.current_position = (0, 0, 0)
        # Alvo se afasta a 6 m/s: contato mais cedo em (100 - 5) / (24 - 6).
        drone.target_position = Mock(side_effect=lambda t: (100 + 6 * t, 0, 0))
        destination = drone.find_intercept(0)
        delay = drone.target_position.call_args.args[0]
        earliest = (100 - constants.EXTERNAL_CONTACT_DISTANCE) / (constants.EXTERNAL_SPEED - 6)
        self.assertGreaterEqual(delay, earliest)
        self.assertLessEqual(delay - earliest, constants.EXTERNAL_INTERCEPT_STEP + 1e-9)
        self.assertAlmostEqual(destination[0], 100 + 6 * delay - constants.EXTERNAL_CONTACT_DISTANCE)
        self.assertLessEqual(math.dist(drone.current_position, destination), constants.EXTERNAL_SPEED * delay)

    def test_target_index_and_contact_without_touching(self):
        drone = self.make_drone()
        with patch.object(constants, 'EXTERNAL_TARGET_INDEX', 3):
            center = drone.flight_plan.get_position(2)
            expected = FlightPlan.position_on_circle(center, constants.FORMATION_RADIUS,
                3 * 360 / constants.DRONE_COUNT + constants.ANGULAR_SPEED * 2)
            self.assertEqual(drone.target_position(2), expected)
        drone.mode = 'seek'
        target = drone.target_position(0)
        position = (target[0] + constants.EXTERNAL_CONTACT_DISTANCE - 0.01, target[1], target[2])
        drone.handle_telemetry(SimpleNamespace(current_position=position))
        self.assertEqual(drone.mode, 'away')
        self.assertGreater(math.dist(position, target), 0)

    def test_repeated_cycles_with_core_and_real_mobility(self):
        builder = SimulationBuilder(SimulationConfiguration(duration=40))
        mobility = MobilityHandler()
        builder.add_handler(TimerHandler())
        builder.add_handler(mobility)
        for index in range(constants.DRONE_COUNT):
            builder.add_node(MovableCoreUAVProtocol, FlightPlan.position_on_circle(
                constants.FLIGHT_PLAN_POINTS[0], constants.FORMATION_RADIUS,
                index * 360 / constants.DRONE_COUNT))
        external_id = builder.add_node(MovableExternalUAVProtocol, (-30, 0, 0))
        contacts = []
        departures = []
        seeks = []
        original_away = MovableExternalUAVProtocol.start_away
        original_seek = MovableExternalUAVProtocol.find_intercept

        def away(drone, now):
            if drone.mode == 'seek':
                contacts.append(math.dist(drone.current_position, drone.target_position(now)))
            departures.append(now)
            return original_away(drone, now)

        def seek(drone, now):
            seeks.append((now, departures[-1]))
            return original_seek(drone, now)

        with patch.object(MovableExternalUAVProtocol, 'start_away', away), \
             patch.object(MovableExternalUAVProtocol, 'find_intercept', seek), \
             patch('movable_external_uav_protocol.random.uniform', return_value=0):
            builder.build().start_simulation()
        self.assertGreaterEqual(len(contacts), 2)
        self.assertTrue(all(distance <= constants.EXTERNAL_CONTACT_DISTANCE for distance in contacts))
        self.assertTrue(all(now - start >= constants.EXTERNAL_AWAY_DURATION - 1e-8 for now, start in seeks))
        self.assertEqual(mobility.speeds[external_id], constants.EXTERNAL_SPEED)


if __name__ == '__main__':
    unittest.main()
