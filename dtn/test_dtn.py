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
from vertical_uav_protocol import VerticalUAVProtocol


class DTNTests(unittest.TestCase):
    def node(self, cls, identifier):
        node = cls()
        node.provider = Mock()
        node.provider.get_id.return_value = identifier
        node.provider.current_time.return_value = 0
        with patch('node_protocol.VisualizationController'):
            node.initialize()
        if hasattr(node, 'current_position'):
            node.handle_telemetry(SimpleNamespace(current_position=(0, 0, 0)))
        return node

    def packet(self, node):
        return node.provider.send_communication_command.call_args.args[0].message

    def test_store_carry_forward_after_lost_question_and_answer(self):
        tower = self.node(TowerProtocol, 0)
        relay = self.node(HorizontalUAVProtocol, 1)
        final = self.node(FinalUAVProtocol, 5)
        tower.sendQuestion()  # Sem contato: a tentativa inicial se perde.
        question = self.packet(tower)
        tower.provider.current_time.return_value = 5
        tower.sendQuestion()
        retried = tower.provider.send_communication_command.call_args_list[-2].args[0].message
        self.assertEqual(retried, question)
        relay.provider.current_time.return_value = 5
        relay.handle_packet(retried)
        relay.handle_packet(retried)
        self.assertEqual(relay.received, 1)
        self.assertEqual(len(relay.communicationCommands), 1)
        relay.moveAndSendMessage()  # Ainda desconectado do destino.
        relay.provider.current_time.return_value = 20
        relay.moveAndSendMessage()  # Contato posterior, carregando a mesma mensagem.
        final.provider.current_time.return_value = 20
        final.handle_packet(self.packet(relay))
        final.handle_packet(self.packet(relay))
        self.assertEqual(final.received, 1)
        self.assertEqual(len(final.communicationCommands), 1)
        answer = self.packet(final)  # Resposta imediata se perde.
        final.provider.current_time.return_value = 30
        final.moveAndSendMessage()
        self.assertEqual(self.packet(final), answer)
        relay.provider.current_time.return_value = 30
        relay.handle_packet(self.packet(final))
        relay.moveAndSendMessage()
        tower.provider.current_time.return_value = 30
        tower.handle_packet(self.packet(relay))
        tower.handle_packet(self.packet(relay))
        self.assertEqual(tower.received, 1)
        self.assertEqual(tower.lastResponse, answer.split('[RESPOSTA]', 1)[1].strip())

    def test_absolute_expiration_and_no_revival(self):
        tower = self.node(TowerProtocol, 0)
        relay = self.node(HorizontalUAVProtocol, 1)
        tower.sendQuestion()
        question = self.packet(tower)
        relay.handle_packet(question)
        relay.provider.current_time.return_value = 59
        relay.moveAndSendMessage()
        self.assertEqual(relay.getMessageMetadata(self.packet(relay))[2], '60')
        relay.provider.send_communication_command.reset_mock()
        relay.provider.current_time.return_value = 60
        relay.moveAndSendMessage()
        relay.handle_packet(question)
        self.assertFalse(relay.communicationCommands)
        self.assertFalse(relay.seenMessages)
        relay.provider.send_communication_command.assert_not_called()
        tower.provider.current_time.return_value = 60
        tower.sendQuestion()
        self.assertEqual(len(tower.communicationCommands), 1)
        self.assertNotEqual(self.packet(tower), question)

    def test_direction_and_invalid_metadata(self):
        relay = self.node(HorizontalUAVProtocol, 1)
        for packet in ('invalid', '[0][PERGUNTA] Sem ID',
                       '[0][ID=0:1][EXP=nan][PERGUNTA] Inválida',
                       '[2][ID=0:1][EXP=60][PERGUNTA] Voltando',
                       '[0][ID=5:1][EXP=60][RESPOSTA] Subindo'):
            relay.handle_packet(packet)
        self.assertEqual(relay.received, 0)
        self.assertFalse(relay.communicationCommands)

    def test_final_retries_stop_at_expiration(self):
        tower = self.node(TowerProtocol, 0)
        final = self.node(FinalUAVProtocol, 5)
        tower.sendQuestion()
        final.handle_packet(self.packet(tower))
        final.provider.send_communication_command.reset_mock()
        final.provider.current_time.return_value = 60
        final.moveAndSendMessage()
        self.assertFalse(final.communicationCommands)
        final.provider.send_communication_command.assert_not_called()

    def test_original_files_and_visual_constants_preserved(self):
        root = Path(__file__).resolve().parents[1]
        for name in ('main.py', 'horizontal_uav_protocol.py', 'vertical_uav_protocol.py'):
            self.assertEqual((root/'broadcast'/name).read_bytes(), (root/'dtn'/name).read_bytes())
        original = {}
        exec((root/'broadcast'/'constants.py').read_text(encoding='utf-8'), original)
        for name, value in original.items():
            if name.isupper():
                self.assertEqual(getattr(constants, name), value, name)

    def test_visual_colors_size_and_mobility(self):
        node = self.node(HorizontalUAVProtocol, 1)
        for kind, color in ((constants.QUESTION_RECEIVED, constants.QUESTION_COLOR),
                            (constants.ANSWER_RECEIVED, constants.ANSWER_COLOR),
                            (constants.NO_MESSAGE_RECEIVED, constants.UAV_COLOR)):
            node.messageReceivedType = kind
            node.setColorAndSize()
            node.visualization.paint_node.assert_called_with(1, color)
            node.visualization.resize_nodes.assert_called_with(constants.DEFAULT_SIZE)
        for cls, identifier in ((HorizontalUAVProtocol, 1), (VerticalUAVProtocol, 3)):
            node = self.node(cls, identifier)
            node.moveAndSendMessage()
            node.provider.send_mobility_command.assert_called_once()
            self.assertEqual(node.provider.schedule_timer.call_args.args[0], 'mobility')

    def test_integrated_original_main_with_losses(self):
        # A adaptação para testar fica aqui; main.py permanece igual ao original.
        simulations = []
        configuration = main.SimulationConfiguration
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
             patch.object(main, 'SimulationConfiguration',
                          side_effect=lambda **kwargs: configuration(duration=80, real_time=False)):
            main.main()
        simulation = simulations[0]
        tower = simulation.get_node(0).protocol_encapsulator.protocol
        self.assertGreater(tower.received, 0)
        self.assertIsNotNone(tower.lastResponse)
        for identifier in range(7):
            node = simulation.get_node(identifier).protocol_encapsulator.protocol
            self.assertTrue(all(node.isMessageValid(c.message) for c in node.communicationCommands))
        print(f'Torre: {tower.received} respostas únicas em 80 segundos (semente 7).')


if __name__ == '__main__':
    unittest.main()
