import json
import math
import random
import unittest
from collections import Counter
from unittest.mock import patch

from gradysim.protocol.messages.communication import CommunicationCommandType
from gradysim.simulator.handler.communication import CommunicationHandler, CommunicationMedium
from gradysim.simulator.handler.mobility import MobilityHandler, MobilityConfiguration
from gradysim.simulator.handler.timer import TimerHandler
from gradysim.simulator.simulation import SimulationBuilder, SimulationConfiguration

import constants
from communicable_uav_protocol import CommunicableUAVProtocol
from flight_plan import FlightPlan
from message_transmitter_uav_protocol import MessageTransmitterUAVProtocol
from simulation_metrics import MetricsHandler, SimulationMetrics


class RandomNetworkTest(unittest.TestCase):
    def test_radio_discovery_delivery_and_lost_discovery_packets(self):
        for seed, drop_type in ((7, None), (19, None), (7, 'position_request'),
                                (7, 'position_plan'), (7, 'contact_ready')):
            with self.subTest(seed=seed, drop_type=drop_type), patch.object(constants, 'SIMULATION_MODE', constants.RANDOM):
                metrics = SimulationMetrics()
                mobility = MobilityHandler(MobilityConfiguration(update_rate=constants.RANDOM_MOVEMENT_INTERVAL))
                unicasts = Counter()
                contact_distances = []

                class ObservedCommunication(CommunicationHandler):
                    def handle_command(handler, command, sender, medium=None):
                        packet = json.loads(command.message)
                        if packet.get('type') == drop_type:
                            return
                        if packet.get('type', 'data') == 'data':
                            self.assertEqual(command.command_type, CommunicationCommandType.SEND)
                            if sender.id < constants.DRONE_COUNT:
                                self.assertEqual(command.destination,
                                    constants.EXTERNAL_CORE_TARGETS[packet['destination_external_index']])
                                unicasts[sender.id, packet['message_id']] += 1
                            else:
                                self.assertEqual(command.destination,
                                    constants.EXTERNAL_CORE_TARGETS[packet['source_external_index']])
                                contact_distances.append(math.dist(sender.position,
                                    mobility.nodes[command.destination].position))
                        super().handle_command(command, sender, medium)

                builder = SimulationBuilder(SimulationConfiguration(duration=180, execution_logging=False))
                builder.add_handler(TimerHandler())
                builder.add_handler(MetricsHandler(metrics))
                builder.add_handler(ObservedCommunication(CommunicationMedium(transmission_range=constants.RADIO_RANGE)))
                builder.add_handler(mobility)
                center = (0, 0, 0)
                for index in range(constants.DRONE_COUNT):
                    builder.add_node(MessageTransmitterUAVProtocol, FlightPlan.position_on_circle(
                        center, constants.FORMATION_RADIUS, index * 360 / constants.DRONE_COUNT))
                for index, offset in enumerate(((40, 0, 0), (-40, 0, 0), (0, 40, 0), (0, -40, 0))):
                    builder.add_node(CommunicableUAVProtocol.with_external(index),
                                     tuple(c + d for c, d in zip(center, offset)))
                rng = random.Random(seed)
                with patch('random.uniform', side_effect=rng.uniform), patch('simulation_metrics.print'):
                    builder.build().start_simulation()
                stats = metrics.summary()
                if drop_type is not None:
                    self.assertEqual(stats['total']['emitted'], 0)
                    self.assertEqual(stats['total']['received'], 0)
                    reason = 'intercept_failed' if drop_type == 'contact_ready' else 'no_response'
                    self.assertGreater(stats['total']['discovery'].get(reason, 0), 0)
                    continue
                self.assertTrue(contact_distances)
                # Telemetria e envio podem ficar separados por um passo de mobilidade.
                contact_tolerance = ((constants.EXTERNAL_SPEED + constants.RANDOM_SPEED)
                                     * constants.RANDOM_MOVEMENT_INTERVAL)
                self.assertLessEqual(max(contact_distances),
                                     constants.EXTERNAL_CONTACT_DISTANCE + contact_tolerance)
                self.assertLessEqual(max(contact_distances), constants.RADIO_RANGE)
                self.assertTrue(unicasts)
                self.assertTrue(all(count == 1 for count in unicasts.values()))
                self.assertGreater(stats['total']['received'], 0)
                self.assertGreater(stats['total']['confirmed'], 0)
                self.assertGreater(stats['total']['discovery']['started'], 0)
                print(f"RANDOM seed={seed}: {stats['total']['received']}/{stats['total']['emitted']} entregues")


if __name__ == '__main__':
    unittest.main()
