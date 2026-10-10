import json
import math
import random
import unittest
from collections import Counter
from unittest.mock import Mock, patch

from gradysim.simulator.handler.communication import CommunicationHandler, CommunicationMedium
from gradysim.simulator.handler.mobility import MobilityHandler
from gradysim.simulator.handler.timer import TimerHandler
from gradysim.simulator.simulation import SimulationBuilder, SimulationConfiguration

import constants
from communicable_uav_protocol import CommunicableUAVProtocol
from flight_plan import FlightPlan
from message_transmitter_uav_protocol import MessageTransmitterUAVProtocol
from movable_core_uav_protocol import MovableCoreUAVProtocol
from movable_external_uav_protocol import MovableExternalUAVProtocol


class ContactExchangeTest(unittest.TestCase):
    def setUp(self):
        self.core = MessageTransmitterUAVProtocol()
        self.core.provider = Mock()
        self.core.provider.get_id.return_value = 2
        with patch.object(MovableCoreUAVProtocol, 'initialize'):
            self.core.initialize()
        self.core.flight_plan = FlightPlan(constants.FLIGHT_PLAN_POINTS, constants.CENTER_SPEED,
                                           constants.EXTERNAL_CORE_TARGETS, constants.DRONE_COUNT)
        self.core.show_message_color = Mock()
        self.external = CommunicableUAVProtocol.with_external(1)()
        self.external.provider = Mock()
        self.external.provider.current_time.return_value = 0
        self.external.provider.get_id.return_value = 27  # Não depende da ordem dos externos no builder.
        with patch('visible_node_protocol.VisualizationController'):
            self.external.initialize()
        self.external.current_position = self.external.contact_position(0)
        self.external.steer = Mock()

    def data(self, message_id='0:1', **fields):
        return dict(type='data', message_id=message_id, source_external_index=0,
                    destination_external_index=1, source_color=[0, 114, 178], payload='o pato', **fields)

    def receive_core(self, packet):
        self.core.handle_packet(json.dumps(packet))

    def control(self, kind='presence', **fields):
        return dict(type=kind, external_index=1, node_id=27, session_id=1, **fields)

    def last_core_packet(self):
        command = self.core.provider.send_communication_command.call_args.args[0]
        self.assertEqual(command.destination, 27)
        return json.loads(command.message)

    def test_queue_delivery_ack_and_departure(self):
        self.receive_core(self.data())
        self.core.provider.send_communication_command.assert_not_called()
        self.external.start_away(0)
        self.assertEqual(self.external.mode, 'contact')
        self.receive_core(self.control())
        delivery = self.last_core_packet()
        self.assertEqual(delivery['type'], 'delivery')
        self.assertIn('0:1', self.core.pending_messages)
        self.external.handle_packet(json.dumps(delivery))
        self.assertEqual(self.external.mode, 'contact')
        self.assertEqual(self.external.received_messages['0:1'], self.data())
        ack = json.loads(self.external.provider.send_communication_command.call_args.args[0].message)
        self.receive_core(ack)
        self.assertEqual(self.core.pending_messages, {})
        complete = self.last_core_packet()
        self.assertEqual(complete['type'], 'contact_complete')
        self.external.handle_packet(json.dumps(complete))
        self.assertEqual(self.external.mode, 'away')
        self.receive_core(self.data())
        self.assertEqual(self.core.pending_messages, {})

    def test_lost_ack_retries_without_duplicate_delivery(self):
        self.receive_core(self.data())
        self.external.start_away(0)
        self.receive_core(self.control())
        delivery = self.last_core_packet()
        with patch('communicable_uav_protocol.logging.info') as log:
            self.external.handle_packet(json.dumps(delivery))
            # O primeiro ACK se perde: a próxima presença repete a entrega.
            self.receive_core(self.control())
            self.external.handle_packet(json.dumps(self.last_core_packet()))
        self.assertEqual(len(self.external.received_messages), 1)
        self.assertEqual(log.call_count, 1)
        ack = json.loads(self.external.provider.send_communication_command.call_args.args[0].message)
        self.receive_core(ack)
        self.assertEqual(self.core.pending_messages, {})
        # Se o encerramento se perder, uma nova presença também o recupera.
        self.receive_core(self.control())
        self.assertEqual(self.last_core_packet()['type'], 'contact_complete')

    def test_external_color_lasts_one_second_even_after_departure(self):
        original_color = self.external.color
        self.receive_core(self.data())
        self.external.start_away(0)
        self.receive_core(self.control())
        self.external.provider.current_time.return_value = 0.25
        self.external.handle_packet(json.dumps(self.last_core_packet()))
        self.assertEqual(self.external.currentColor, tuple(self.data()['source_color']))
        self.assertEqual(self.external.color, original_color)
        self.external.provider.schedule_timer.assert_called_with(constants.RESTORE_COLOR_TIMER, 1.25)
        ack = json.loads(self.external.provider.send_communication_command.call_args.args[0].message)
        self.receive_core(ack)
        self.external.handle_packet(json.dumps(self.last_core_packet()))
        self.assertEqual(self.external.mode, 'away')
        self.external.provider.current_time.return_value = 1.0
        self.external.handle_timer(constants.REPAINT_TIMER)
        self.assertEqual(self.external.currentColor, tuple(self.data()['source_color']))
        self.external.provider.current_time.return_value = 1.25
        self.external.handle_timer(constants.RESTORE_COLOR_TIMER)
        self.assertEqual(self.external.currentColor, original_color)

    def test_empty_queue_completes_contact(self):
        self.external.start_away(0)
        self.receive_core(self.control())
        self.external.handle_packet(json.dumps(self.last_core_packet()))
        self.assertEqual(self.external.mode, 'away')

    def test_timeout_keeps_queue_for_next_visit_and_rejects_stale_packets(self):
        self.receive_core(self.data())
        self.external.start_away(0)
        self.receive_core(self.control())
        old_delivery = self.last_core_packet()
        self.external.provider.current_time.return_value = constants.EXTERNAL_CONTACT_RETRY_INTERVAL
        self.external.handle_timer(constants.CONTACT_TIMER)
        retry = json.loads(self.external.provider.send_communication_command.call_args.args[0].message)
        self.assertEqual(retry['type'], 'presence')
        self.external.provider.current_time.return_value = constants.EXTERNAL_CONTACT_TIMEOUT
        self.external.handle_timer(constants.CONTACT_TIMER)
        self.assertEqual(self.external.mode, 'away')
        self.assertIn('0:1', self.core.pending_messages)
        self.external.handle_packet(json.dumps(old_delivery))
        self.assertEqual(self.external.received_messages, {})
        with patch.object(self.external, 'in_contact', return_value=True):
            self.external.start_away(3)
        self.external.handle_packet(json.dumps(old_delivery))
        self.assertEqual(self.external.received_messages, {})
        presence = self.control()
        presence['session_id'] = 2
        self.receive_core(presence)
        self.receive_core(self.control('ack', message_id='0:1'))
        self.assertIn('0:1', self.core.pending_messages)
        self.external.handle_packet(json.dumps(self.last_core_packet()))
        ack = json.loads(self.external.provider.send_communication_command.call_args.args[0].message)
        self.receive_core(ack)
        self.assertEqual(self.core.pending_messages, {})

    def test_invalid_or_unoffered_ack_does_not_remove_messages(self):
        self.receive_core(self.data())
        self.receive_core(self.control('ack', message_id='0:1'))
        self.assertIn('0:1', self.core.pending_messages)
        self.receive_core(self.control())
        for overrides in ({'external_index': 0}, {'session_id': 2}, {'node_id': 28},
                          {'message_id': []}, {'external_index': True}):
            ack = self.control('ack', message_id='0:1')
            ack.update(overrides)
            self.receive_core(ack)
            self.assertIn('0:1', self.core.pending_messages)

    def test_multiple_pending_messages_require_all_confirmations(self):
        for message_id in ('0:1', '0:2'):
            self.receive_core(self.data(message_id))
        self.receive_core(self.control())
        self.core.provider.send_communication_command.reset_mock()
        self.receive_core(self.control('ack', message_id='0:1'))
        self.core.provider.send_communication_command.assert_not_called()
        self.assertEqual(set(self.core.pending_messages), {'0:2'})
        self.receive_core(self.control('ack', message_id='0:2'))
        self.assertEqual(self.last_core_packet()['type'], 'contact_complete')

    def test_moving_simulation_delivers_with_dropped_control_packets(self):
        for drop_kind in (None, 'presence', 'delivery', 'ack', 'contact_complete', 'all_responses'):
            with self.subTest(drop_kind=drop_kind):
                dropped = []
                cores, externals = [], []
                accepted = Counter()
                violations = []

                class RecordingCore(MessageTransmitterUAVProtocol):
                    def initialize(node):
                        super().initialize()
                        cores.append(node)

                class RecordingExternal(CommunicableUAVProtocol):
                    def initialize(node):
                        super().initialize()
                        externals.append(node)

                    def handle_packet(node, message):
                        before = set(node.received_messages)
                        super().handle_packet(message)
                        accepted.update(set(node.received_messages) - before)

                    def handle_telemetry(node, telemetry):
                        now = node.provider.current_time()
                        center = node.flight_plan.get_position(now)
                        if math.dist(telemetry.current_position[:2], center[:2]) < constants.FORMATION_RADIUS + constants.SAFETY_MARGIN:
                            violations.append((now, node.external_index))
                        super().handle_telemetry(telemetry)

                class LossyCommunication(CommunicationHandler):
                    def handle_command(handler, command, sender, medium=None):
                        packet = json.loads(command.message)
                        if ((packet.get('type') == drop_kind and not dropped)
                                or (drop_kind == 'all_responses'
                                    and packet.get('type') in ('delivery', 'contact_complete'))):
                            dropped.append(packet)
                            return
                        super().handle_command(command, sender, medium)

                builder = SimulationBuilder(SimulationConfiguration(duration=60, execution_logging=False))
                builder.add_handler(TimerHandler())
                builder.add_handler(LossyCommunication(CommunicationMedium(transmission_range=constants.RADIO_RANGE)))
                builder.add_handler(MobilityHandler())
                center = constants.FLIGHT_PLAN_POINTS[0]
                for index in range(constants.DRONE_COUNT):
                    builder.add_node(RecordingCore, FlightPlan.position_on_circle(
                        center, constants.FORMATION_RADIUS, index * 360 / constants.DRONE_COUNT))
                for index, offset in enumerate(((30, 0, 0), (-30, 0, 0), (0, 30, 0), (0, -30, 0))):
                    builder.add_node(RecordingExternal.with_external(index),
                                     tuple(c + d for c, d in zip(center, offset)))
                rng = random.Random(19)
                with patch('movable_external_uav_protocol.random.uniform', side_effect=rng.uniform), \
                     patch('logging.info'):
                    builder.build().start_simulation()
                if drop_kind == 'all_responses':
                    self.assertTrue(dropped)
                    self.assertTrue(all(node.message_sequence >= 2 for node in externals))
                    self.assertTrue(all(not node.received_messages for node in externals))
                    self.assertTrue(any(node.pending_messages for node in cores))
                    self.assertEqual(violations, [])
                    continue
                if drop_kind is not None:
                    self.assertEqual(len(dropped), 1)
                self.assertEqual(violations, [])
                self.assertTrue(all(node.received_messages for node in externals))
                self.assertTrue(all(count == 1 for count in accepted.values()))
                for node in externals:
                    for packet in node.received_messages.values():
                        self.assertEqual(packet['destination_external_index'], node.external_index)
                confirmed = set().union(*(node.confirmed_messages for node in cores))
                self.assertTrue(confirmed)
                self.assertTrue(confirmed <= set(accepted))
                pending = set().union(*(set(node.pending_messages) for node in cores))
                self.assertTrue(confirmed.isdisjoint(pending))


if __name__ == '__main__':
    unittest.main()
