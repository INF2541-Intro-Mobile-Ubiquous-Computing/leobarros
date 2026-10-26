import math
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from gradysim.simulator.simulation import SimulationBuilder, SimulationConfiguration
from gradysim.simulator.handler.timer import TimerHandler
from gradysim.simulator.handler.mobility import MobilityHandler
from movable_external_uav_protocol import MovableExternalUAVProtocol
import constants


class ExternalMovementTest(unittest.TestCase):
    def make_drone(self, index):
        drone = MovableExternalUAVProtocol.with_external(index)()
        drone.provider = Mock()
        drone.provider.current_time.return_value = 0
        with patch('visible_node_protocol.VisualizationController'):
            drone.initialize()
        return drone

    def test_all_sides_approach_wait_and_return_exactly_thirty_metres(self):
        for mode in (constants.TOPOLOGY, constants.RANDOM):
            for index in range(4):
                with self.subTest(mode=mode, index=index), patch.object(constants, 'SIMULATION_MODE', mode):
                    drone = self.make_drone(index)
                    self.assertAlmostEqual(math.dist(drone.contact_point, drone.away_point), 30)
                    drone.handle_telemetry(SimpleNamespace(current_position=drone.away_point))
                    self.assertEqual(drone.mode, 'seek')
                    self.assertEqual(drone.destination, drone.contact_point)
                    drone.handle_telemetry(SimpleNamespace(current_position=drone.contact_point))
                    self.assertEqual(drone.mode, 'waiting')
                    for now in (1, 10, 100):
                        drone.provider.current_time.return_value = now
                        drone.handle_timer(constants.MOVEMENT_TIMER)
                        self.assertEqual(drone.mode, 'waiting')
                        self.assertEqual(drone.destination, drone.contact_point)
                    drone.start_away(100)
                    self.assertEqual(drone.destination, drone.away_point)
                    drone.provider.current_time.return_value = 1000
                    drone.handle_timer(constants.MOVEMENT_TIMER)
                    self.assertEqual(drone.mode, 'away')  # O retorno depende da posição, não do tempo.
                    drone.handle_telemetry(SimpleNamespace(current_position=drone.away_point))
                    self.assertEqual(drone.mode, 'seek')
                    self.assertEqual(drone.destination, drone.contact_point)

    def test_main_starts_satellites_at_cardinal_endpoints(self):
        import main
        with patch.object(main, 'SimulationBuilder') as builder, patch.object(main, 'PacedVisualizationHandler'):
            main.main()
        calls = builder.return_value.add_node.call_args_list[-4:]
        for index, call in enumerate(calls):
            self.assertEqual(call.args[0].external_index, index)
            self.assertEqual(call.args[1], MovableExternalUAVProtocol.station_position(index, True))
            self.assertAlmostEqual(math.dist(call.args[1], (0, 0, 0)), 63)

    def test_real_mobility_stays_on_each_segment_over_repeated_cycles(self):
        samples = {i: [] for i in range(4)}
        visits = {i: 0 for i in range(4)}

        class Satellite(MovableExternalUAVProtocol):
            def wait_for_core(node, now):
                visits[node.external_index] += 1
                node.start_away(now)

            def handle_telemetry(node, telemetry):
                samples[node.external_index].append(telemetry.current_position)
                super().handle_telemetry(telemetry)

        builder = SimulationBuilder(SimulationConfiguration(duration=12, execution_logging=False))
        builder.add_handler(TimerHandler())
        builder.add_handler(MobilityHandler())
        for index in range(4):
            builder.add_node(Satellite.with_external(index), Satellite.station_position(index, True))
        builder.build().start_simulation()
        for index, positions in samples.items():
            direction = constants.EXTERNAL_DIRECTIONS[index]
            self.assertGreaterEqual(visits[index], 3)
            for position in positions:
                radius = sum(p*d for p, d in zip(position, direction))
                self.assertGreaterEqual(radius, 33 - 1e-8)
                self.assertLessEqual(radius, 63 + 1e-8)
                self.assertLess(math.dist(position, tuple(radius*d for d in direction)), 1e-8)


if __name__ == '__main__':
    unittest.main()
