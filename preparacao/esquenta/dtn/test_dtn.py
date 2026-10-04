import random
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import constants
from gradysim.protocol.messages.communication import CommunicationCommandType
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

    def test_store_carry_forward_on_hello(self):
        tower = self.node(TowerProtocol, 0)
        relay = self.node(HorizontalUAVProtocol, 10)
        final = self.node(FinalUAVProtocol, 20)
        tower.sendQuestion()
        question = tower.communicationCommands[0].message
        tower.provider.send_communication_command.assert_not_called()
        tower.provider.current_time.return_value = 10000
        tower.handle_packet('[HELLO=10]')
        self.assertEqual(self.packet(tower), question)
        self.assertEqual(tower.provider.send_communication_command.call_args.args[0].destination, 10)
        self.assertFalse(tower.communicationCommands)
        relay.handle_packet(question)
        relay.handle_packet(question)
        self.assertEqual(relay.received, 1)
        self.assertEqual(len(relay.communicationCommands), 1)
        relay.handle_timer('mobility')
        relay.provider.send_communication_command.assert_not_called()
        relay.provider.current_time.return_value = 20000
        relay.handle_packet('[HELLO=20]')
        final.handle_packet(self.packet(relay))
        final.handle_packet(self.packet(relay))
        self.assertEqual(final.received, 1)
        self.assertEqual(len(final.communicationCommands), 1)
        final.provider.send_communication_command.assert_not_called()
        final.handle_packet('[HELLO=10]')
        answer = self.packet(final)
        self.assertNotEqual(final.getMessageMetadata(answer)[1], final.getMessageMetadata(question)[1])
        relay.handle_packet(answer)
        relay.handle_packet('[HELLO=0]')
        tower.handle_packet(self.packet(relay))
        tower.handle_packet(self.packet(relay))
        self.assertEqual(tower.received, 1)
        self.assertEqual(tower.lastResponse, answer.split('[RESPOSTA]', 1)[1].strip())

    def test_whole_queue_sent_once_without_ack(self):
        tower = self.node(TowerProtocol, 0)
        for _ in range(3):
            tower.sendQuestion()
        messages = [command.message for command in tower.communicationCommands]
        self.assertEqual(len({tower.getMessageMetadata(m)[1] for m in messages}), 3)
        tower.handle_packet('[HELLO=10]')
        commands = [call.args[0] for call in tower.provider.send_communication_command.call_args_list]
        self.assertEqual([command.message for command in commands], messages)
        self.assertTrue(all(command.command_type == CommunicationCommandType.SEND and
                            command.destination == 10 for command in commands))
        self.assertEqual(tower.sent, 3)
        self.assertFalse(tower.communicationCommands)
        # Mesmo sem entregar os dados, novos HELLOs não causam reenvio.
        tower.handle_packet('[HELLO=10]')
        tower.handle_packet('[HELLO=20]')
        self.assertEqual(tower.provider.send_communication_command.call_count, 3)

    def test_no_expiration_and_duplicates_after_forwarding(self):
        relay = self.node(HorizontalUAVProtocol, 10)
        message = '[ID=0:1][PERGUNTA] teste'
        relay.handle_packet(message)
        relay.provider.current_time.return_value = 1000000
        relay.handle_timer('mobility')
        self.assertEqual(len(relay.communicationCommands), 1)
        relay.handle_packet('[HELLO=20]')
        relay.handle_packet(message)
        self.assertFalse(relay.communicationCommands)
        self.assertEqual(relay.received, 1)
        self.assertEqual(relay.sent, 1)
        own = relay.createMessage('[RESPOSTA] teste')
        relay.handle_packet(own)
        self.assertFalse(relay.communicationCommands)

    def test_hello_timer_and_invalid_packets(self):
        for cls in (TowerProtocol, HorizontalUAVProtocol, FinalUAVProtocol):
            node = self.node(cls, 10)
            node.provider.current_time.return_value = 7
            node.handle_timer('hello')
            command = node.provider.send_communication_command.call_args.args[0]
            self.assertEqual(command.command_type, CommunicationCommandType.BROADCAST)
            self.assertEqual(command.message, '[HELLO=10]')
            node.provider.schedule_timer.assert_called_with('hello', 7 + constants.HELLO_INTERVAL)
            self.assertEqual(node.sent, 0)  # Contador de dados, sem anúncios.
            node.scheduleForwardMessage(node.createMessage('[PERGUNTA] teste'))
            node.provider.send_communication_command.reset_mock()
            for message in ('[HELLO=10]', '[HELLO=x]', '[HELLO=-1]', '[HELLO=20]extra',
                            '[PERGUNTA] sem ID', '[ID=][RESPOSTA] inválida'):
                node.handle_packet(message)
            node.provider.send_communication_command.assert_not_called()
            self.assertEqual(len(node.communicationCommands), 1)
            self.assertEqual(node.received, 0)

    def test_command_exception_keeps_message(self):
        tower = self.node(TowerProtocol, 0)
        tower.sendQuestion()
        tower.provider.send_communication_command.side_effect = RuntimeError('falha local')
        with self.assertRaises(RuntimeError):
            tower.handle_packet('[HELLO=10]')
        self.assertEqual(len(tower.communicationCommands), 1)
        self.assertEqual(tower.sent, 0)

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
            node.handle_timer('mobility')
            node.provider.send_mobility_command.assert_called_once()
            self.assertEqual(node.provider.schedule_timer.call_args.args[0], 'mobility')

    def test_integrated_original_main_with_losses(self):
        # A adaptação para testar fica aqui; main.py permanece igual ao original.
        simulations = []
        configuration = main.SimulationConfiguration
        transmissions = []
        handle_command = main.CommunicationHandler.handle_command

        def record_command(handler, command, sender, *args, **kwargs):
            transmissions.append((sender.id, command.command_type, command.message, command.destination))
            return handle_command(handler, command, sender, *args, **kwargs)

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
             patch.object(main.CommunicationHandler, 'handle_command', record_command), \
             patch.object(main, 'SimulationConfiguration',
                          side_effect=lambda **kwargs: configuration(duration=80, real_time=False)):
            main.main()
        simulation = simulations[0]
        tower = simulation.get_node(0).protocol_encapsulator.protocol
        self.assertGreater(tower.sent, 0)
        self.assertTrue(any(simulation.get_node(i).protocol_encapsulator.protocol.received > 0
                            for i in range(1, 7)))
        sent = set()
        for sender, kind, message, destination in transmissions:
            if message.startswith('[HELLO='):
                self.assertEqual(kind, CommunicationCommandType.BROADCAST)
            else:
                self.assertEqual(kind, CommunicationCommandType.SEND)
                self.assertIsNotNone(destination)
                key = (sender, tower.getMessageMetadata(message)[1])
                self.assertNotIn(key, sent)
                sent.add(key)
        for identifier in range(7):
            node = simulation.get_node(identifier).protocol_encapsulator.protocol
            self.assertTrue(all(node.getMessageMetadata(c.message)[1] in node.seenMessages
                                for c in node.communicationCommands))
        print(f'Torre: {tower.received} respostas únicas em 80 segundos (semente 7).')

    def test_integrated_delivery_with_direct_contact(self):
        builder = main.SimulationBuilder(main.SimulationConfiguration(duration=20, real_time=False))
        builder.add_node(TowerProtocol, (0, 0, 0))
        builder.add_node(FinalUAVProtocol, (0, 0, 0))
        builder.add_handler(main.CommunicationHandler(main.CommunicationMedium(
            transmission_range=1000, delay=0.1, failure_rate=0)))
        builder.add_handler(main.TimerHandler())
        builder.add_handler(main.MobilityHandler())
        simulation = builder.build()
        simulation.start_simulation()
        tower = simulation.get_node(0).protocol_encapsulator.protocol
        self.assertGreater(tower.received, 0)
        self.assertIsNotNone(tower.lastResponse)


if __name__ == '__main__':
    unittest.main()
