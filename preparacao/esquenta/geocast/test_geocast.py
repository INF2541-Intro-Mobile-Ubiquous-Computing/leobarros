import json
import random
import unittest
from collections import deque
from types import SimpleNamespace
from unittest.mock import Mock, patch

import constants
import main
from node_protocol import NodeProtocol
from uav_protocol import UAVProtocol
from final_uav_protocol import FinalUAVProtocol
from horizontal_uav_protocol import HorizontalUAVProtocol
from tower_protocol import TowerProtocol
from gradysim.protocol.messages.communication import CommunicationCommandType


class GeocastTests(unittest.TestCase):
    def node(self, cls, identifier, position=None):
        node = cls()
        node.provider = Mock()
        node.provider.get_id.return_value = identifier
        node.provider.current_time.return_value = 0
        with patch('node_protocol.VisualizationController'):
            node.initialize()
        if position is not None:
            node.handle_telemetry(SimpleNamespace(current_position=position))
        return node

    def hello(self, node, identifier, position):
        node.handle_packet(json.dumps({'type': 'HELLO', 'sender': identifier, 'position': position}))

    def question(self, identifier='question-1', region=(0, 50, 30, 50)):
        return {'id': identifier, 'type': 'PERGUNTA', 'region': region,
                'reply_region': (0, 0, -50, -50), 'text': 'Teste'}

    def test_boundaries_and_unknown_position(self):
        node = self.node(NodeProtocol, 100)
        region = constants.GEOCAST_REGION
        self.assertFalse(node.isInGeocastRegion(region))
        for position in ((0, 30, 0), (50, 50, 0), (0, 50, 0), (50, 30, 0), (25, 40, 100)):
            node.handle_telemetry(SimpleNamespace(current_position=position))
            self.assertTrue(node.isInGeocastRegion(region))
        for position in ((-0.01, 40, 0), (50.01, 40, 0), (25, 29.99, 0), (25, 50.01, 0)):
            node.handle_telemetry(SimpleNamespace(current_position=position))
            self.assertFalse(node.isInGeocastRegion(region))

    def test_hello_discovers_positions_but_does_not_send_data(self):
        node = self.node(HorizontalUAVProtocol, 100, (0, 0, 0))
        node.handle_timer('hello')
        command = node.provider.send_communication_command.call_args.args[0]
        self.assertEqual(command.command_type, CommunicationCommandType.BROADCAST)
        self.assertEqual(json.loads(command.message), {'type': 'HELLO', 'sender': 100, 'position': [0, 0, 0]})
        node.provider.schedule_timer.assert_called_with('hello', constants.HELLO_INTERVAL)
        node.provider.send_communication_command.reset_mock()
        self.hello(node, 101, (10, 20, 0))
        self.assertEqual(node.neighbors[101], ([10, 20, 0], 0))
        self.hello(node, 100, (0, 0, 0))
        self.assertNotIn(100, node.neighbors)
        node.provider.send_communication_command.assert_not_called()
        self.assertEqual(node.sent, 0)

    def test_outside_selects_closest_progressing_neighbor(self):
        node = self.node(HorizontalUAVProtocol, 100, (0, -20, 0))
        self.hello(node, 101, (0, -40, 0))
        self.hello(node, 102, (0, 0, 0))
        self.hello(node, 103, (0, 20, 0))
        packet = self.question()
        node.handle_packet(json.dumps(packet))
        command = node.provider.send_communication_command.call_args.args[0]
        self.assertEqual(command.command_type, CommunicationCommandType.SEND)
        self.assertEqual(command.destination, 103)
        self.assertEqual(json.loads(command.message)['id'], packet['id'])
        self.assertEqual(node.sent, 1)
        node.handle_packet(json.dumps(packet))
        self.assertEqual(node.provider.send_communication_command.call_count, 1)
        self.assertEqual(node.received, 1)

    def test_inside_distributes_only_to_inside_neighbors(self):
        node = self.node(NodeProtocol, 100, (10, 40, 0))
        self.hello(node, 101, (0, 30, 0))
        self.hello(node, 102, (50, 50, 0))
        self.hello(node, 103, (-1, 40, 0))
        node.deliverMessage = Mock()
        packet = self.question()
        node.handle_packet(json.dumps(packet))
        commands = [call.args[0] for call in node.provider.send_communication_command.call_args_list]
        self.assertEqual({c.destination for c in commands}, {101, 102})
        self.assertTrue(all(c.command_type == CommunicationCommandType.SEND for c in commands))
        node.deliverMessage.assert_called_once()
        node.handle_packet(json.dumps(packet))
        self.assertEqual(node.sent, 2)
        node.deliverMessage.assert_called_once()

    def test_packet_region_and_current_position_control_delivery(self):
        node = self.node(NodeProtocol, 100, (-100, -100, 0))
        node.deliverMessage = Mock()
        packet = self.question(region=(-101, -99, -101, -99))
        node.handle_packet(json.dumps(packet))
        node.deliverMessage.assert_called_once()
        node.handle_telemetry(SimpleNamespace(current_position=(20, 40, 0)))
        packet['id'] = 'question-2'
        node.handle_packet(json.dumps(packet))
        node.deliverMessage.assert_called_once()

    def test_no_progress_no_contact_and_expired_contact_drop_without_queue(self):
        for neighbor in (None, (0, -40, 0), (0, -20, 0), (0, 20, 0)):
            node = self.node(HorizontalUAVProtocol, 100, (0, -20, 0))
            if neighbor is not None:
                self.hello(node, 101, neighbor)
            if neighbor == (0, 20, 0):
                node.provider.current_time.return_value = constants.NEIGHBOR_TIMEOUT
            packet = self.question()
            node.handle_packet(json.dumps(packet))
            node.provider.send_communication_command.assert_not_called()
            self.hello(node, 102, (0, 40, 0))
            node.handle_timer('mobility')
            node.handle_packet(json.dumps(packet))
            node.provider.send_communication_command.assert_not_called()
            self.assertFalse(hasattr(node, 'communicationCommands'))
            self.assertFalse(hasattr(node, 'level'))

    def test_invalid_packets_are_ignored(self):
        node = self.node(NodeProtocol, 100, (0, 0, 0))
        packets = [None, [], {}, {'type': 'HELLO', 'sender': 1, 'position': [1]},
                   {'type': 'HELLO', 'sender': 1, 'position': [float('nan'), 0, 0]}]
        for field, value in (('id', []), ('region', [50, 0, 30, 50]),
                             ('region', [0, 50, 30]), ('reply_region', None), ('text', None)):
            packet = self.question()
            packet[field] = value
            packets.append(packet)
        for packet in packets:
            node.handle_packet(json.dumps(packet))
        node.handle_packet('invalid json')
        self.assertFalse(node.neighbors)
        self.assertFalse(node.seenMessageIds)
        node.provider.send_communication_command.assert_not_called()

    def test_multihop_delivery_distribution_and_replies_without_duplicates(self):
        nodes = {0: self.node(TowerProtocol, 0, (0, -50, 0)),
                 40: self.node(HorizontalUAVProtocol, 40, (0, 0, 0)),
                 80: self.node(FinalUAVProtocol, 80, (10, 40, 0)),
                 81: self.node(FinalUAVProtocol, 81, (30, 40, 0))}
        links = {0: [40], 40: [0, 80, 81], 80: [40, 81], 81: [40, 80]}
        pending = deque()  # Transporte simulado do teste; os protocolos não têm filas.
        history = []
        deliveries = []
        for identifier, node in nodes.items():
            for neighbor in links[identifier]:
                self.hello(node, neighbor, nodes[neighbor].current_position)
            def send(command, sender=identifier):
                history.append((sender, command))
                pending.append(command)
            node.provider.send_communication_command.side_effect = send
            original = node.deliverMessage
            def deliver(packet, identifier=identifier, original=original):
                deliveries.append((identifier, packet['id'], packet['type']))
                original(packet)
            node.deliverMessage = deliver
        nodes[0].sendQuestion()
        first = json.loads(history[0][1].message)
        for _ in range(50):
            if not pending:
                break
            command = pending.popleft()
            self.assertEqual(command.command_type, CommunicationCommandType.SEND)
            nodes[command.destination].handle_packet(command.message)
        self.assertFalse(pending)
        question_deliveries = [identifier for identifier, _, kind in deliveries if kind == 'PERGUNTA']
        self.assertEqual(sorted(question_deliveries), [80, 81])
        self.assertEqual(len([d for d in deliveries if d[0] == 0 and d[2] == 'RESPOSTA']), 2)
        self.assertIsNotNone(nodes[0].lastResponse)
        attempts = [(sender, json.loads(command.message)['id'], command.destination) for sender, command in history]
        self.assertEqual(len(attempts), len(set(attempts)))
        nodes[0].handle_packet(json.dumps(first))
        self.assertFalse(pending)
        nodes[0].sendQuestion()
        self.assertNotEqual(json.loads(history[-1][1].message)['id'], first['id'])

    def test_integrated_geocast_with_losses(self):
        simulations, deliveries, transmissions = [], [], []
        configuration = main.SimulationConfiguration
        original_delivery = UAVProtocol.deliverMessage
        original_command = main.CommunicationHandler.handle_command
        def record_delivery(node, packet):
            if packet['type'] == 'PERGUNTA':
                deliveries.append((node.provider.get_id(), packet['id'], node.current_position, packet['region']))
            original_delivery(node, packet)
        def record_command(handler, command, sender, *args, **kwargs):
            transmissions.append((sender.id, command.command_type, json.loads(command.message), command.destination))
            return original_command(handler, command, sender, *args, **kwargs)
        class TestBuilder(main.SimulationBuilder):
            def add_handler(self, handler):
                if handler is not None:
                    return super().add_handler(handler)
            def build(self):
                simulation = super().build()
                simulations.append(simulation)
                return simulation
        random.seed(7)
        with patch.object(main, 'SimulationBuilder', TestBuilder), \
             patch.object(main, 'VisualizationHandler', return_value=None), \
             patch.object(main, 'SimulationConfiguration', side_effect=lambda **kwargs:
                          configuration(duration=80, real_time=False, execution_logging=False)), \
             patch.object(UAVProtocol, 'deliverMessage', record_delivery), \
             patch.object(main.CommunicationHandler, 'handle_command', record_command):
            main.main()
        self.assertTrue(deliveries)
        self.assertTrue(all(NodeProtocol.distanceToRegion(position, region) == 0
                            for _, _, position, region in deliveries))
        delivered_ids = [(node, identifier) for node, identifier, _, _ in deliveries]
        self.assertEqual(len(delivered_ids), len(set(delivered_ids)))
        attempts = []
        for sender, kind, packet, destination in transmissions:
            if packet['type'] == 'HELLO':
                self.assertEqual(kind, CommunicationCommandType.BROADCAST)
            else:
                self.assertEqual(kind, CommunicationCommandType.SEND)
                self.assertIsNotNone(destination)
                attempts.append((sender, packet['id'], destination))
        self.assertEqual(len(attempts), len(set(attempts)))
        tower = simulations[0].get_node(0).protocol_encapsulator.protocol
        self.assertIsNotNone(tower.lastResponse)
        print(f'Geocast: {len(deliveries)} perguntas entregues na região; {tower.received} pacotes recebidos pela torre.')


if __name__ == '__main__':
    unittest.main()
