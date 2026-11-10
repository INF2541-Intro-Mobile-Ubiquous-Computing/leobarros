import json
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
from gradysim.protocol.messages.communication import CommunicationCommandType


class MessageRoutingTest(unittest.TestCase):
    def setUp(self):
        mode = patch.object(constants, 'SIMULATION_MODE', constants.TOPOLOGY)
        mode.start()
        self.addCleanup(mode.stop)

    def plan(self):
        return FlightPlan()

    def packet(self, **overrides):
        packet = dict(message_id='0:1', source_external_index=0,
                      destination_external_index=1, payload='o pato')
        packet.update(overrides)
        return json.dumps(packet)

    def core(self, index, plan):
        node = MessageTransmitterUAVProtocol()
        node.provider = Mock()
        node.provider.get_id.return_value = index
        node.provider.current_time.return_value = 0
        with patch('visible_node_protocol.VisualizationController'):
            node.initialize()
        node.flight_plan = plan
        return node

    def test_every_core_stores_and_broadcasts_once_in_both_modes(self):
        for mode in (constants.TOPOLOGY, constants.RANDOM):
            for index in range(constants.DRONE_COUNT):
                with self.subTest(mode=mode, index=index), patch.object(constants, 'SIMULATION_MODE', mode):
                    node = self.core(index, self.plan())
                    self.assertEqual(node.currentColor, (0, 0, 0))
                    node.handle_packet(self.packet())
                    node.handle_packet(self.packet())
                    self.assertEqual(node.received_messages, {'0:1': json.loads(self.packet())})
                    self.assertEqual(node.pending_messages, node.received_messages)
                    node.provider.send_communication_command.assert_called_once()
                    command = node.provider.send_communication_command.call_args.args[0]
                    self.assertEqual(command.command_type, CommunicationCommandType.BROADCAST)
                    self.assertIsNone(command.destination)
                    self.assertEqual(json.loads(command.message), json.loads(self.packet()))

    def test_invalid_packets_are_discarded(self):
        for message in ('o pato', '[]', '{}', 'null', self.packet(destination_external_index=99),
                        self.packet(destination_external_index=True),
                        self.packet(source_external_index=-1), self.packet(payload=None),
                        self.packet(source_color=[256, 0, 0]), self.packet(source_color=None),
                        self.packet(message_id='')):
            with self.subTest(message=message):
                node = self.core(0, self.plan())
                with self.assertLogs(level='WARNING'):
                    node.handle_packet(message)
                node.provider.send_communication_command.assert_not_called()
                self.assertIsNone(node.temporary_color)

    def test_color_restores_black_one_second_after_receipt(self):
        for index in range(constants.DRONE_COUNT):
            with self.subTest(index=index):
                node = self.core(index, self.plan())
                original_color = node.color
                self.assertEqual(original_color, (0, 0, 0))
                node.provider.current_time.return_value = 0.25
                node.handle_packet(self.packet(source_color=[12, 34, 56]))
                node.visualization.paint_node.assert_called_with(index, (12, 34, 56))
                node.provider.schedule_timer.assert_called_with(constants.RESTORE_COLOR_TIMER, 1.25)
                node.provider.current_time.return_value = 1.0
                node.handle_timer(constants.REPAINT_TIMER)
                self.assertEqual(node.currentColor, (12, 34, 56))
                node.provider.current_time.return_value = 1.25
                node.handle_timer(constants.RESTORE_COLOR_TIMER)
                node.visualization.paint_node.assert_called_with(index, original_color)
                self.assertEqual(node.color, original_color)

    def test_new_message_restarts_color_duration(self):
        node = self.core(1, self.plan())
        node.handle_packet(self.packet(source_color=[1, 2, 3]))
        node.provider.current_time.return_value = 0.5
        node.handle_packet(self.packet(message_id='0:2', source_color=[4, 5, 6]))
        node.provider.current_time.return_value = 1.0
        node.handle_timer(constants.RESTORE_COLOR_TIMER)
        self.assertEqual(node.currentColor, (4, 5, 6))
        node.provider.current_time.return_value = 1.5
        node.handle_timer(constants.RESTORE_COLOR_TIMER)
        self.assertEqual(node.currentColor, node.color)

    def test_plan_validates_satellite_indices(self):
        plan = self.plan()
        for index in constants.EXTERNAL_DIRECTIONS:
            self.assertEqual(plan.validate_external_index(index), index)
        for index in (True, -1, 99, '0', None):
            with self.subTest(index=index), self.assertRaises(ValueError):
                plan.validate_external_index(index)

    def test_external_sends_only_to_discovered_core_at_contact(self):
        drone = CommunicableUAVProtocol.with_external(0)()
        drone.provider = Mock()
        drone.provider.get_id.return_value = constants.DRONE_COUNT
        drone.provider.current_time.return_value = 0
        with patch('movable_external_uav_protocol.VisibleNodeProtocol.initialize'):
            drone.initialize()
        self.assertIsNone(drone.target_index)
        drone.start_contact(0)
        drone.provider.send_communication_command.assert_not_called()
        drone.current_position = drone.contact_point
        drone.mode = 'waiting'
        drone.target_index = 5  # Core escolhido pela descoberta.
        drone.start_contact(1)
        drone.start_contact(1.1)
        self.assertEqual(drone.message_sequence, 1)
        drone.mode = 'waiting'
        drone.start_contact(2)
        commands = drone.provider.send_communication_command.call_args_list
        packets = [json.loads(call.args[0].message) for call in commands
                   if json.loads(call.args[0].message)['type'] == 'data']
        self.assertEqual([call.args[0].destination for call in commands], [5, 5, 5, 5])
        self.assertEqual([packet['message_id'] for packet in packets], ['0:1', '0:2'])
        self.assertEqual(packets[0]['source_external_index'], 0)
        self.assertEqual(packets[0]['source_color'], list(drone.color))
        self.assertEqual(packets[0]['destination_external_index'], 1)

    def test_delivery_with_moving_core_and_four_externals(self):
        for seed in (7, 19):
            with self.subTest(seed=seed):
                sent = {}
                routes = defaultdict(list)
                cores = []

                class RecordingCore(MessageTransmitterUAVProtocol):
                    def initialize(node):
                        super().initialize()
                        cores.append(node)

                class RecordingCommunication(CommunicationHandler):
                    def handle_command(self, command, sender, medium=None):
                        if sender.id >= constants.DRONE_COUNT:
                            packet = json.loads(command.message)
                            if packet['type'] == 'data':
                                sent[packet['message_id']] = packet
                        super().handle_command(command, sender, medium)

                builder = SimulationBuilder(SimulationConfiguration(duration=240, execution_logging=False))
                builder.add_handler(TimerHandler())
                builder.add_handler(RecordingCommunication(CommunicationMedium(
                    transmission_range=constants.RADIO_RANGE)))
                builder.add_handler(MobilityHandler())
                center = (0, 0, 0)
                for index in range(constants.DRONE_COUNT):
                    builder.add_node(RecordingCore, FlightPlan.position_on_circle(
                        center, constants.FORMATION_RADIUS, index * 360 / constants.DRONE_COUNT))
                for index, offset in enumerate(((63, 0, 0), (-63, 0, 0), (0, 63, 0), (0, -63, 0))):
                    builder.add_node(CommunicableUAVProtocol.with_external(index),
                                     tuple(c + d for c, d in zip(center, offset)))
                original = MessageTransmitterUAVProtocol.handle_packet

                def receive(node, message):
                    packet = json.loads(message)
                    if packet.get('type', 'data') == 'data':
                        routes[packet['message_id']].append(node.provider.get_id())
                    original(node, message)

                with patch.object(MessageTransmitterUAVProtocol, 'handle_packet', receive):
                    builder.build().start_simulation()
                self.assertEqual({p['source_external_index'] for p in sent.values()}, {0, 1, 2, 3})
                for node in cores:
                    self.assertEqual(node.received_messages, sent)
                for route in routes.values():
                    self.assertEqual(set(route), set(range(constants.DRONE_COUNT)))




if __name__ == '__main__':
    unittest.main()
