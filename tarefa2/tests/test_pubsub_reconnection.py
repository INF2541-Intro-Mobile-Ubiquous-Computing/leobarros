"""TF06: exact application IDs across contacts, loss and peer changes."""
import json
import logging
import unittest

from gradysim.protocol.interface import IProtocol
from gradysim.protocol.messages.communication import BroadcastMessageCommand, SendMessageCommand
from gradysim.simulator.handler.communication import CommunicationMedium
from gradysim.simulator.handler.timer import TimerHandler
from gradysim.simulator.simulation import SimulationBuilder, SimulationConfiguration

from src.pubsub.adapter import PubSubAdapterMixin
from src.pubsub.models import Publication
from src.pubsub.pspeer_mixin import PSPeerMixin
from src.pubsub.radio import PubSubCommunicationHandler
from src.pubsub.satellite_client import PubSubSatelliteMixin
from src.satellite import ST_EXCHANGE, ST_COLLECT_OUT
import test_pubsub_transport as transport_tests


class PubSubReconnectionTests(unittest.TestCase):
    setUp = transport_tests.PubSubTransportTests.setUp

    def run_network(self, switch_peer=False, lose_first=False, lose_report=False,
                    lose_buffered=False, fail_callback=False):
        positions = [(0, 0, 0), (50, 0, 0), (25, 0, 0), (50, 15, 0)]
        snapshots = []

        class Core(PubSubAdapterMixin, transport_tests.test_protocol(0, 0.8, False)):
            def initialize(self):
                super().initialize()
                if self.provider.get_id() == 0:
                    for timer, when in [('publish:first', 0.4), ('publish:offline', 0.7),
                                        ('publish:last', 1.3)]:
                        self.provider.schedule_timer(timer, when)
                if self.provider.get_id() == 1:
                    self.provider.schedule_timer('snapshot', 0.9)

            def handle_timer(self, timer):
                node = self.provider.get_id()
                if timer == 'beacon':
                    self.provider.schedule_timer('beacon', self.provider.current_time() + 0.5)
                    self.provider.send_communication_command(BroadcastMessageCommand(json.dumps({
                        'msg_type': 'core_beacon', 'sender_id': node,
                        'role': 'hub' if node == 2 else 'rim', 'position': positions[node],
                    })))
                elif timer.startswith('publish:'):
                    self.select_pspeer(0)
                    ident = timer.split(':')[1]
                    self.publish_pubsub(Publication(ident, 'T1', 0, 'N',
                                                    self.provider.current_time(), {'id': ident}))
                elif timer == 'snapshot':
                    snapshots.append((dict(self._pubsub_delivery_state),
                                      len(self._core_buffer), self._buffered_for(3)))

        class Peer(PSPeerMixin, Core):
            pspeer_slot = 0

        class SatelliteBase(IProtocol):
            def initialize(self):
                self._state = ST_COLLECT_OUT
                self._ack_node = None
                self.received = []
                self.failed_once = False
                for timer, when in [('connect', 0.2), ('subscribe', 0.3), ('disconnect', 0.5),
                                    ('connect', 1.0), ('disconnect', 1.15), ('connect', 1.6),
                                    ('disconnect', 1.75), ('connect', 2.0), ('fetch', 2.2)]:
                    self.provider.schedule_timer(timer, when)

            def _start_exchange(self, contact):
                self._state = ST_EXCHANGE
                self._ack_node = contact
                self.provider.send_communication_command(SendMessageCommand(json.dumps({
                    'msg_type': 'dock_connect', 'sender_id': 3, 'face': 'N'}), contact))

            def handle_timer(self, timer):
                if timer == 'connect':
                    if switch_peer and self.provider.current_time() == 1.0:
                        self.select_pspeer(0)  # while offline: contact will resume it
                    self._start_exchange(1)
                elif timer == 'subscribe':
                    self.select_pspeer(1)
                    self.subscribe_pubsub('T1', {'N'})
                elif timer == 'disconnect':
                    self.provider.send_communication_command(SendMessageCommand(json.dumps({
                        'msg_type': 'dock_disconnect', 'sender_id': 3}), 1))
                    self._state = ST_COLLECT_OUT
                    self._ack_node = None
                elif timer == 'fetch':
                    self.fetch_pubsub('T1')

            def handle_packet(self, message):
                pass

            def handle_telemetry(self, telemetry):
                pass

            def finish(self):
                pass

        class Satellite(PubSubSatelliteMixin, SatelliteBase):
            def on_pubsub_delivery(self, message):
                if fail_callback and message.publications and not self.failed_once:
                    self.failed_once = True
                    raise RuntimeError('application did not accept delivery')
                self.received.extend((self.provider.current_time(), p.message_id) for p in message.publications)

            def handle_packet(self, message):
                # A failed application callback is observable and must not create
                # a receipt. Catch only our injected error so simulation continues.
                try:
                    super().handle_packet(message)
                except RuntimeError as error:
                    if str(error) != 'application did not accept delivery':
                        raise

        class Radio(PubSubCommunicationHandler):
            def __init__(self):
                super().__init__(CommunicationMedium(transmission_range=30))
                self.fetches = []
                self.pushes = []

            def handle_command(self, command, sender, medium=None):
                packet = json.loads(command.message)
                payload = packet.get('payload', {})
                now = sender.protocol_encapsulator.protocol.provider.current_time()
                if payload.get('operation') == 'FETCH' and sender.id == 3:
                    self.fetches.append((now, packet['destination'], payload['received_ids']))
                    if lose_report and now == 1.0:
                        return
                if payload.get('operation') == 'DELIVER' and packet.get('source_id') == sender.id:
                    self.pushes.append((now, payload.get('is_push'), payload['publications']))
                    if lose_first and now == 0.4:
                        return
                    if lose_buffered and now == 1.0 and payload.get('is_push'):
                        return
                return super().handle_command(command, sender, medium)

        builder = SimulationBuilder(SimulationConfiguration(duration=2.4))
        for index, position in enumerate(positions):
            builder.add_node(Peer if index < 2 else Core if index == 2 else Satellite, position)
        radio = Radio()
        builder.add_handler(TimerHandler())
        builder.add_handler(radio)
        simulation = builder.build()
        logging.getLogger().setLevel(logging.CRITICAL)
        simulation.start_simulation()
        nodes = [simulation.get_node(i).protocol_encapsulator.protocol for i in range(4)]
        return nodes, radio, snapshots

    def assert_received_once(self, nodes):
        self.assertEqual([ident for _, ident in nodes[3].received], ['first', 'offline', 'last'])
        self.assertEqual(nodes[3]._received_ids, {'T1': {'first', 'offline', 'last'}})

    def test_tf06_repeated_contacts_deliver_only_exact_unread_ids(self):
        nodes, radio, snapshots = self.run_network()
        self.assert_received_once(nodes)
        self.assertEqual(nodes[3].received, [(0.4, 'first'), (1.0, 'offline'), (1.6, 'last')])
        self.assertEqual(snapshots[0][1:], (1, []))
        self.assertIn('pending', snapshots[0][0].values())
        self.assertEqual(nodes[1]._core_buffer, {})
        self.assertEqual(set(nodes[1]._pubsub_delivery_state.values()), {'submitted'})
        self.assertEqual(nodes[1].pspeer_service.fetch(3, 'T1'), ())
        self.assertEqual(radio.fetches[-1][2], ['first', 'last', 'offline'])

    def test_peer_change_rebinds_identical_filter_and_carries_receipt_ledger(self):
        nodes, radio, _ = self.run_network(switch_peer=True)
        self.assert_received_once(nodes)
        self.assertEqual(nodes[0].pspeer_service.fetch(3, 'T1'), ())
        self.assertTrue(all(dest == 0 for when, dest, _ in radio.fetches if when >= 1.0))
        item = Publication('next', 'T1', 0, 'N', 3, {})
        self.assertEqual(nodes[0].pspeer_service.delivery_subscribers(item, 0), (3,))
        self.assertEqual(nodes[1].pspeer_service.delivery_subscribers(item, 1), ())

    def test_lost_send_does_not_consume_and_fetch_recovers(self):
        nodes, _, _ = self.run_network(lose_first=True)
        self.assertCountEqual([ident for _, ident in nodes[3].received], ['first', 'offline', 'last'])
        self.assertEqual(len(nodes[3].received), 3)
        self.assertTrue(all(when >= 1.0 for when, _ in nodes[3].received))

    def test_lost_receipt_report_is_repeated_at_next_contact_without_duplicate_callback(self):
        nodes, radio, _ = self.run_network(lose_report=True)
        self.assert_received_once(nodes)
        self.assertIn((1.0, 1, ['first']), radio.fetches)
        self.assertIn((1.6, 1, ['first', 'offline']), radio.fetches)
        self.assertEqual(nodes[1].pspeer_service.fetch(3, 'T1'), ())

    def test_buffer_removal_after_send_is_not_receipt_and_fetch_still_recovers(self):
        nodes, _, _ = self.run_network(lose_buffered=True)
        self.assert_received_once(nodes)
        self.assertEqual(nodes[1]._core_buffer, {})

    def test_failed_application_callback_does_not_record_receipt(self):
        nodes, _, _ = self.run_network(fail_callback=True)
        self.assertEqual(len(nodes[3].received), 3)
        self.assertCountEqual([ident for _, ident in nodes[3].received], ['first', 'offline', 'last'])
        self.assertTrue(all(when >= 1.0 for when, _ in nodes[3].received))
