import random
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import constants
import main
from final_uav_protocol import FinalUAVProtocol
from horizontal_uav_protocol import HorizontalUAVProtocol
from tower_protocol import TowerProtocol


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

    def test_boundaries_inside_outside_and_unknown_position(self):
        node = self.node(HorizontalUAVProtocol, 1)
        self.assertFalse(node.isInGeocastRegion())
        for position in ((0, 30, 0), (50, 50, 0), (0, 50, 0), (50, 30, 0), (25, 40, 0)):
            node.handle_telemetry(SimpleNamespace(current_position=position))
            self.assertTrue(node.isInGeocastRegion(), position)
        for position in ((-0.01, 40, 0), (50.01, 40, 0), (25, 29.99, 0), (25, 50.01, 0)):
            node.handle_telemetry(SimpleNamespace(current_position=position))
            self.assertFalse(node.isInGeocastRegion(), position)

    def test_final_enters_and_leaves_region(self):
        node = self.node(FinalUAVProtocol, 5)
        question = '[2][PERGUNTA] Teste'
        for position, expected in ((None, 0), ((-1, 40, 0), 0), ((1, 40, 0), 1), ((-1, 40, 0), 1)):
            if position is not None:
                node.handle_telemetry(SimpleNamespace(current_position=position))
            node.handle_packet(question)
            self.assertEqual(node.sent, expected)
            self.assertEqual(node.received, expected)

    def test_outside_relay_forwards_without_answering(self):
        node = self.node(HorizontalUAVProtocol, 1, (0, -20, 0))
        node.handle_packet('[0][PERGUNTA] Teste')
        self.assertEqual([c.message for c in node.communicationCommands], ['[1][0][PERGUNTA] Teste'])
        node.moveAndSendMessage()
        self.assertEqual(node.sent, 1)
        self.assertFalse(node.communicationCommands)

    def test_inside_intermediate_answers_and_still_forwards(self):
        node = self.node(HorizontalUAVProtocol, 1, (25, 40, 0))
        node.handle_packet('[0][PERGUNTA] Teste')
        messages = [c.message for c in node.communicationCommands]
        self.assertEqual(len(messages), 2)
        self.assertIn('[RESPOSTA]', messages[0])
        self.assertEqual(messages[1], '[1][0][PERGUNTA] Teste')

    def test_reply_returns_through_outside_relay_to_tower(self):
        final = self.node(FinalUAVProtocol, 5, (25, 40, 0))
        relay = self.node(HorizontalUAVProtocol, 1, (0, -20, 0))
        tower = self.node(TowerProtocol, 0)
        final.handle_packet('[2][PERGUNTA] Teste')
        relay.handle_packet(final.provider.send_communication_command.call_args.args[0].message)
        relay.moveAndSendMessage()
        tower.handle_packet(relay.provider.send_communication_command.call_args.args[0].message)
        self.assertEqual(tower.received, 1)
        self.assertIsNotNone(tower.lastResponse)

    def test_direction_rules_preserved_inside_region(self):
        final = self.node(FinalUAVProtocol, 5, (25, 40, 0))
        for packet in ('[3][PERGUNTA] Teste', '[2][RESPOSTA] Teste', 'Inválida'):
            final.handle_packet(packet)
        self.assertEqual(final.sent, 0)
        relay = self.node(HorizontalUAVProtocol, 1, (25, 40, 0))
        relay.handle_packet('[2][PERGUNTA] Teste')
        relay.handle_packet('[0][RESPOSTA] Teste')
        self.assertFalse(relay.communicationCommands)

    def test_original_files_and_appearance_preserved(self):
        root = Path(__file__).resolve().parents[1]
        for name in ('main.py', 'node_protocol.py', 'tower_protocol.py',
                     'horizontal_uav_protocol.py', 'vertical_uav_protocol.py'):
            self.assertEqual((root/'broadcast'/name).read_bytes(), (root/'geocast'/name).read_bytes())
        original = {}
        exec((root/'broadcast'/'constants.py').read_text(encoding='utf-8'), original)
        for name, value in original.items():
            if name.isupper():
                self.assertEqual(getattr(constants, name), value)
        node = self.node(HorizontalUAVProtocol, 1)
        for kind, color in ((constants.QUESTION_RECEIVED, constants.QUESTION_COLOR),
                            (constants.ANSWER_RECEIVED, constants.ANSWER_COLOR),
                            (constants.NO_MESSAGE_RECEIVED, constants.UAV_COLOR)):
            node.messageReceivedType = kind
            node.setColorAndSize()
            node.visualization.paint_node.assert_called_with(1, color)
            node.visualization.resize_nodes.assert_called_with(constants.DEFAULT_SIZE)

    def run_simulation(self, region):
        simulations = []
        deliveries = []
        configuration = main.SimulationConfiguration
        original_handle = FinalUAVProtocol.handle_packet
        def record(node, message):
            before = node.sent
            original_handle(node, message)
            if node.sent > before:
                deliveries.append(node.current_position)
        class TestBuilder(main.SimulationBuilder):
            def add_handler(self, handler):
                if handler is not None:
                    return super().add_handler(handler)
            def build(self):
                result = super().build()
                simulations.append(result)
                return result
        random.seed(7)
        with patch.object(main, 'SimulationBuilder', TestBuilder), \
             patch.object(main, 'VisualizationHandler', return_value=None), \
             patch.object(main, 'SimulationConfiguration', side_effect=lambda **kwargs:
                          configuration(duration=80, real_time=False, execution_logging=False)), \
             patch.object(constants, 'GEOCAST_REGION', region), \
             patch.object(FinalUAVProtocol, 'handle_packet', record):
            main.main()
        return simulations[0], deliveries

    def test_integrated_delivery_only_inside_region_with_losses(self):
        simulation, deliveries = self.run_simulation(constants.GEOCAST_REGION)
        self.assertTrue(deliveries)
        self.assertTrue(all(0 <= x <= 50 and 30 <= y <= 50 for x, y, z in deliveries))
        tower = simulation.get_node(0).protocol_encapsulator.protocol
        self.assertGreater(tower.received, 0)
        print(f'Região padrão: {len(deliveries)} respostas geradas; {tower.received} recebidas na torre.')

    def test_integrated_unoccupied_region_has_no_answers(self):
        simulation, deliveries = self.run_simulation((100, 110, 100, 110))
        self.assertFalse(deliveries)
        self.assertEqual(simulation.get_node(0).protocol_encapsulator.protocol.received, 0)


if __name__ == '__main__':
    unittest.main()
