import json
import random
import unittest
from collections import defaultdict
from unittest.mock import Mock, patch

from gradysim.simulator.handler.communication import CommunicationHandler, CommunicationMedium
from gradysim.simulator.handler.mobility import MobilityHandler
from gradysim.simulator.handler.timer import TimerHandler
from gradysim.simulator.simulation import SimulationBuilder, SimulationConfiguration

import constants
from communicable_uav_protocol import CommunicableUAVProtocol
from flight_plan import FlightPlan
from message_transmitter_uav_protocol import MessageTransmitterUAVProtocol
from movable_external_uav_protocol import MovableExternalUAVProtocol


class MessageRoutingTest(unittest.TestCase):
    def plan(self, targets=None, count=9):
        return FlightPlan(constants.FLIGHT_PLAN_POINTS, constants.CENTER_SPEED,
                          targets if targets is not None else constants.EXTERNAL_CORE_TARGETS, count)

    def packet(self, **overrides):
        packet = dict(message_id='0:1', source_external_index=0,
                      destination_external_index=1, payload='o pato')
        packet.update(overrides)
        return json.dumps(packet)

    def core(self, index, plan):
        node = MessageTransmitterUAVProtocol()
        node.provider = Mock()
        node.provider.get_id.return_value = index
        node.flight_plan = plan
        return node

    def test_routes_and_stop_at_target(self):
        for count, route in ((9, [2, 3, 4]), (9, [2, 1, 0, 8]),
                             (9, [8, 0, 1]), (9, [4]), (8, [0, 1, 2, 3, 4])):
            with self.subTest(route=route), patch.object(constants, 'DRONE_COUNT', count):
                plan = self.plan({0: route[0], 1: route[-1]}, count)
                message = self.packet()
                for index, current in enumerate(route):
                    node = self.core(current, plan)
                    with self.assertLogs(level='INFO') as logs:
                        node.handle_packet(message)
                    if index == len(route) - 1:
                        node.provider.send_communication_command.assert_not_called()
                        self.assertIn('recebida no core alvo', logs.output[0])
                    else:
                        command = node.provider.send_communication_command.call_args.args[0]
                        self.assertEqual(command.destination, route[index + 1])
                        self.assertEqual(command.message, message)

    def test_invalid_packets_are_discarded(self):
        for message in ('o pato', '[]', '{}', 'null', self.packet(destination_external_index=99),
                        self.packet(destination_external_index=True),
                        self.packet(source_external_index=-1), self.packet(payload=None),
                        self.packet(message_id='')):
            with self.subTest(message=message):
                node = self.core(0, self.plan())
                with self.assertLogs(level='WARNING'):
                    node.handle_packet(message)
                node.provider.send_communication_command.assert_not_called()

    def test_plan_validates_and_copies_mapping(self):
        targets = {0: 8}
        plan = self.plan(targets)
        targets[0] = 2
        self.assertEqual(plan.get_core_target(0), 8)
        with self.assertRaises(ValueError):
            plan.get_core_target(1)
        for targets in ({0: 9}, {-1: 0}, {0: -1}, {0: '2'}):
            with self.subTest(targets=targets), self.assertRaises(ValueError):
                self.plan(targets)

    def test_external_uses_mapping_and_sends_only_at_contact(self):
        drone = CommunicableUAVProtocol.with_external(0)()
        drone.provider = Mock()
        drone.provider.current_time.return_value = 0
        with patch.object(constants, 'EXTERNAL_CORE_TARGETS', {0: 8, 1: 2}), \
             patch('movable_external_uav_protocol.VisibleNodeProtocol.initialize'):
            drone.initialize()
        self.assertEqual(drone.target_index, 8)
        with patch.object(MovableExternalUAVProtocol, 'start_away'), \
             patch.object(drone, 'in_contact', return_value=False):
            drone.start_away(0)
        drone.provider.send_communication_command.assert_not_called()
        with patch.object(MovableExternalUAVProtocol, 'start_away'), \
             patch.object(drone, 'in_contact', return_value=True):
            drone.start_away(1)
            drone.start_away(2)
        commands = drone.provider.send_communication_command.call_args_list
        packets = [json.loads(call.args[0].message) for call in commands]
        self.assertEqual([call.args[0].destination for call in commands], [8, 8])
        self.assertEqual([packet['message_id'] for packet in packets], ['0:1', '0:2'])
        self.assertEqual(packets[0]['source_external_index'], 0)
        self.assertEqual(packets[0]['destination_external_index'], 1)

    def test_delivery_with_moving_core_and_four_externals(self):
        for seed in (7, 19):
            with self.subTest(seed=seed):
                sent = {}
                routes = defaultdict(list)
                delivered = []

                class RecordingCommunication(CommunicationHandler):
                    def handle_command(self, command, sender, medium=None):
                        if sender.id >= constants.DRONE_COUNT:
                            packet = json.loads(command.message)
                            sent[packet['message_id']] = packet
                        super().handle_command(command, sender, medium)

                builder = SimulationBuilder(SimulationConfiguration(duration=60, execution_logging=False))
                builder.add_handler(TimerHandler())
                builder.add_handler(RecordingCommunication(CommunicationMedium(
                    transmission_range=constants.RADIO_RANGE)))
                builder.add_handler(MobilityHandler())
                center = constants.FLIGHT_PLAN_POINTS[0]
                for index in range(constants.DRONE_COUNT):
                    builder.add_node(MessageTransmitterUAVProtocol, FlightPlan.position_on_circle(
                        center, constants.FORMATION_RADIUS, index * 360 / constants.DRONE_COUNT))
                for index, offset in enumerate(((30, 0, 0), (-30, 0, 0), (0, 30, 0), (0, -30, 0))):
                    builder.add_node(CommunicableUAVProtocol.with_external(index),
                                     tuple(c + d for c, d in zip(center, offset)))
                original = MessageTransmitterUAVProtocol.handle_packet

                def receive(node, message):
                    packet = json.loads(message)
                    routes[packet['message_id']].append(node.provider.get_id())
                    original(node, message)

                def observe_log(template, *args):
                    if 'recebida no core alvo' in template:
                        delivered.append(args[0])

                rng = random.Random(seed)
                with patch.object(MessageTransmitterUAVProtocol, 'handle_packet', receive), \
                     patch('movable_external_uav_protocol.random.uniform', side_effect=rng.uniform), \
                     patch('message_transmitter_uav_protocol.logging.info', side_effect=observe_log):
                    builder.build().start_simulation()
                self.assertEqual({p['source_external_index'] for p in sent.values()}, {0, 1, 2, 3})
                self.assertCountEqual(delivered, sent.keys())
                expected_routes = {0: [0, 1, 2], 1: [2, 1, 0], 2: [4, 5, 6], 3: [6, 5, 4]}
                for message_id, packet in sent.items():
                    self.assertEqual(routes[message_id], expected_routes[packet['source_external_index']])


if __name__ == '__main__':
    unittest.main()
