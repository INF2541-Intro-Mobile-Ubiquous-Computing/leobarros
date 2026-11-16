"""Reproducible dynamic filters, TF05 and offline satellite coalescing."""
import json
import logging
import random
import unittest
from unittest.mock import Mock, patch

from gradysim.protocol.interface import IProtocol
from gradysim.protocol.messages.communication import BroadcastMessageCommand, SendMessageCommand
from gradysim.simulator.handler.communication import CommunicationMedium
from gradysim.simulator.handler.timer import TimerHandler
from gradysim.simulator.simulation import SimulationBuilder, SimulationConfiguration

from src.pubsub.adapter import PubSubAdapterMixin
from src.pubsub.dynamic_subscriptions import DynamicSubscriptionMixin
from src.pubsub.models import Publication, Region, SubscribeEnvelope
from src.pubsub.pspeer_mixin import PSPeerMixin
from src.pubsub.radio import PubSubCommunicationHandler
from src.pubsub.satellite_client import PubSubSatelliteMixin
from src.satellite import ST_COLLECT_OUT, ST_EXCHANGE
from src.uav import make_core_hub, make_core_rim, make_satellite
import test_pubsub_transport as transport_tests


class DynamicSubscriptionTests(unittest.TestCase):
    setUp = transport_tests.PubSubTransportTests.setUp

    def client(self, node=1, seed=2056, interval=5, can_send=True):
        class Base:
            def initialize(self):
                pass

            def handle_timer(self, timer):
                self.other_timer = timer

        class Client(DynamicSubscriptionMixin, PubSubAdapterMixin, Base):
            pass

        client = Client()
        client.provider = Mock()
        client.provider.get_id.return_value = node
        client.provider.current_time.return_value = 0
        client.send_pubsub = Mock(return_value=can_send)
        with (patch('src.pubsub.dynamic_subscriptions.PUBSUB_SEED', seed),
              patch('src.pubsub.dynamic_subscriptions.PUBSUB_SUBSCRIPTION_INTERVAL', interval)):
            client.initialize()
        client.select_pspeer(8)
        return client

    def generate(self, client, count=30):
        for index in range(count):
            client.provider.current_time.return_value = (index + 1) * client._subscription_interval
            client.handle_timer(client.subscription_timer)
        return [c.args[1] for c in client.send_pubsub.call_args_list if isinstance(c.args[1], SubscribeEnvelope)]

    def test_seeded_filters_reproduce_and_keep_both_topic_subscriptions(self):
        state = random.getstate()
        first, other = self.client(1), self.client(2)
        sequence = self.generate(first)
        self.generate(other)
        self.assertEqual(sequence, self.generate(self.client(1)))
        self.assertNotEqual(sequence, self.generate(self.client(1, seed=9)))
        self.assertEqual(set(first._client_subscriptions), {'T1', 'T2'})
        self.assertTrue(all(1 <= len(m.subscription.accepted_regions) <= 5 for m in sequence))
        self.assertGreater(len({m.subscription.accepted_regions for m in sequence}), 1)
        self.assertEqual(random.getstate(), state)

    def test_interval_forwarding_and_failed_submission_retains_filter_without_fetch(self):
        client = self.client(interval=2, can_send=False)
        self.generate(client, 3)
        self.assertEqual(client.send_pubsub.call_count, 3)  # SUBSCRIBE only, no FETCH
        self.assertTrue(client._client_subscriptions)
        client.provider.schedule_timer.assert_called_with('pubsub_subscribe', 8)
        client.handle_timer('movement')
        self.assertEqual(client.other_timer, 'movement')

    def test_invalid_intervals_are_rejected(self):
        for value in (0, -1, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                self.client(interval=value)

    def test_factories_enable_dynamic_subscriptions_only_in_pubsub_mode(self):
        factories = (lambda enabled: make_core_hub('swcore', pubsub=enabled),
                     lambda enabled: make_core_rim(0, 'swcore', pubsub=enabled),
                     lambda enabled: make_satellite('N', swcore=True, pubsub=enabled))
        for factory in factories:
            self.assertFalse(issubclass(factory(False), DynamicSubscriptionMixin))
            self.assertTrue(issubclass(factory(True), DynamicSubscriptionMixin))

    def run_network(self, satellite=False, drop_subscribe=False):
        received = []
        local_snapshots = []

        class Core(PubSubAdapterMixin, transport_tests.test_protocol(2, 0.9, False)):
            def initialize(self):
                super().initialize()
                self.provider.schedule_timer('beacon', 0.01)
                if self.provider.get_id() == 0:
                    for timer, when in [('old:C:T1', 0.1), ('old:N:T1', 0.12),
                                        ('old:N:T2', 0.14), ('old:S:T2', 0.16), ('new:N:T1', 0.95),
                                        ('end', 1.06)]:
                        self.provider.schedule_timer(timer, when)

            def handle_timer(self, timer):
                if timer == 'beacon':
                    node = self.provider.get_id()
                    self.provider.send_communication_command(BroadcastMessageCommand(json.dumps({
                        'msg_type': 'core_beacon', 'sender_id': node,
                        'role': 'hub' if node == 1 else 'rim', 'position': [0, 0, 0]})))
                    self.provider.schedule_timer('beacon', self.provider.current_time() + 0.2)
                elif timer.startswith(('old:', 'new:')):
                    _, region, topic = timer.split(':')
                    self.select_pspeer(2)
                    self.publish_pubsub(Publication(timer, topic, 0, region,
                                                    self.provider.current_time(), {}))

        class Peer(PSPeerMixin, Core):
            pspeer_slot = 0

        class SatelliteBase(IProtocol):
            def initialize(self):
                self._state = ST_COLLECT_OUT
                self._ack_node = None
                self.provider.schedule_timer('contact', 0.8)
                self.provider.schedule_timer('snapshot', 0.7)

            def _start_exchange(self, contact):
                self._state = ST_EXCHANGE
                self._ack_node = contact
                self.provider.send_communication_command(SendMessageCommand(json.dumps({
                    'msg_type': 'dock_connect', 'sender_id': 3, 'face': 'N'}), contact))

            def handle_timer(self, timer):
                if timer == 'contact':
                    self._start_exchange(2)
                elif timer == 'snapshot':
                    local_snapshots.append(dict(self._client_subscriptions))

            def handle_packet(self, message):
                pass

            def handle_telemetry(self, telemetry):
                pass

            def finish(self):
                pass

        class Satellite(PubSubSatelliteMixin, SatelliteBase):
            pass

        class Subscriber(DynamicSubscriptionMixin, Satellite if satellite else Core):
            def initialize(self):
                super().initialize()
                self.select_pspeer(2)
                # Force a known sequence to test exact historical eligibility;
                # seeded generation itself is exercised independently above.
                self._subscription_rng = Mock()
                self._subscription_rng.choice.side_effect = ['T1', 'T1', 'T2']
                self._subscription_rng.randint.return_value = 1
                self._subscription_rng.sample.side_effect = [[Region.C], [Region.N], [Region.N]]

            def on_pubsub_delivery(self, message):
                received.extend(p.message_id for p in message.publications)

        class Radio(PubSubCommunicationHandler):
            def __init__(self):
                super().__init__(CommunicationMedium(transmission_range=30))
                self.submissions = []

            def handle_command(self, command, sender, medium=None):
                packet = json.loads(command.message)
                if sender.id == 3 and packet.get('payload', {}).get('operation') == 'SUBSCRIBE':
                    self.submissions.append(packet['payload']['subscription'])
                    if drop_subscribe:
                        return
                return super().handle_command(command, sender, medium)

        builder = SimulationBuilder(SimulationConfiguration(duration=1.05))
        for cls, position in [(Core, (0, 0, 0)), (Core, (25, 0, 0)),
                              (Peer, (50, 0, 0)), (Subscriber, (50, 10, 0))]:
            builder.add_node(cls, position)
        radio = Radio()
        builder.add_handler(TimerHandler())
        builder.add_handler(radio)
        with patch('src.pubsub.dynamic_subscriptions.PUBSUB_SUBSCRIPTION_INTERVAL', 0.3):
            simulation = builder.build()
            logging.getLogger().setLevel(logging.CRITICAL)
            simulation.start_simulation()
        client = simulation.get_node(3).protocol_encapsulator.protocol
        return received, client, radio, local_snapshots

    def test_tf05_core_subscription_fetches_history_then_updates_filter_and_keeps_other_topic(self):
        received, client, radio, _ = self.run_network()
        self.assertEqual(received, ['old:C:T1', 'old:N:T1', 'old:N:T2', 'new:N:T1'])
        self.assertEqual(set(client._client_subscriptions), {'T1', 'T2'})
        self.assertEqual(len(radio.submissions), 3)

    def test_offline_satellite_sends_latest_filter_at_contact_and_receives_eligible_history(self):
        received, client, radio, snapshots = self.run_network(satellite=True)
        self.assertEqual(snapshots[0]['T1'].accepted_regions, frozenset({Region.N}))
        self.assertEqual(received, ['old:N:T1', 'old:N:T2', 'new:N:T1'])
        self.assertEqual(len(radio.submissions), 2)
        self.assertTrue(all(s['accepted_regions'] == ['N'] for s in radio.submissions))
        self.assertEqual(set(client._client_subscriptions), {'T1', 'T2'})

    def test_fetch_applies_current_filter_even_when_subscribe_has_not_arrived(self):
        received, _, _, _ = self.run_network(drop_subscribe=True)
        self.assertEqual(received, ['old:C:T1', 'old:N:T1', 'old:N:T2', 'new:N:T1'])
