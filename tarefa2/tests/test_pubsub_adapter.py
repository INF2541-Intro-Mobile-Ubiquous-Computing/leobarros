"""Stage 13: requests and FETCH replies cross real radio links via the hub."""
import io
import logging
import unittest

from gradysim.simulator.handler.communication import CommunicationHandler, CommunicationMedium
from gradysim.simulator.handler.timer import TimerHandler
from gradysim.simulator.simulation import SimulationBuilder, SimulationConfiguration

from src.pubsub.adapter import PubSubAdapterMixin
from src.pubsub.models import FetchEnvelope, Publication, Region, SubscribeEnvelope, Subscription, SyncEnvelope
from src.pubsub.pspeer_mixin import PSPeerMixin
from src.uav import make_core_hub, make_core_rim
import test_pubsub_transport as transport_tests


class PubSubAdapterTests(unittest.TestCase):
    setUp = transport_tests.PubSubTransportTests.setUp

    def run_network(self, peer=True, selected=2, early=False, invalid=False):
        class Client(PubSubAdapterMixin, transport_tests.test_protocol(2, 0.3, False)):
            def initialize(self):
                super().initialize()
                self.results = []
                self.deliveries = []
                if self.provider.get_id() == 0:
                    if selected is not None:
                        self.select_pspeer(selected)
                    for timer, when in [('subscribe', 0 if early else 0.3),
                                        ('publish', 0.4), ('fetch', 0.5), ('fetch', 0.6)]:
                        self.provider.schedule_timer(timer, when)

            def handle_timer(self, timer):
                if timer == 'subscribe':
                    self.results.append(self.subscribe_pubsub('T1', {Region.N}))
                elif timer == 'publish':
                    for ident, region in [('eligible', Region.N), ('filtered', Region.S)]:
                        self.results.append(self.publish_pubsub(
                            Publication(ident, 'T1', 0, region, 0.4, {'value': 1})))
                    if invalid:
                        self.send_pubsub(2, SubscribeEnvelope(0, Subscription(99, 'T1', {Region.N})))
                        self.send_pubsub(2, SubscribeEnvelope(99, Subscription(99, 'T1', {Region.N})))
                        self.send_pubsub(2, FetchEnvelope(0, 99, 'T1'))
                        self.send_pubsub(2, SyncEnvelope(0, (Subscription(99, 'T1', {Region.N}),)))
                elif timer == 'fetch':
                    self.results.append(self.fetch_pubsub('T1'))
                elif timer != 'send_test':
                    super().handle_timer(timer)

            def on_pubsub_delivery(self, message):
                if not message.is_push:  # these assertions exercise FETCH snapshots
                    self.deliveries.append(message)

        class Peer(PSPeerMixin, Client):
            pspeer_slot = 0

        builder = SimulationBuilder(SimulationConfiguration(duration=0.8))
        for index, x in enumerate((0, 25, 50)):
            builder.add_node(Peer if peer and index == 2 else Client, (x, 0, 0))
        builder.add_handler(TimerHandler())
        builder.add_handler(CommunicationHandler(CommunicationMedium(transmission_range=30)))
        simulation = builder.build()
        output = io.StringIO()
        handler = logging.StreamHandler(output)
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.DEBUG)
        simulation.start_simulation()
        self.logs = output.getvalue()
        return [simulation.get_node(n).protocol_encapsulator.protocol for n in range(3)]

    def test_requests_and_repeated_fetch_reply_via_hub_without_consumption(self):
        client, hub, peer = self.run_network()
        self.assertTrue(all(client.results))
        self.assertEqual([[p.message_id for p in m.publications] for m in client.deliveries],
                         [['eligible'], ['eligible']])
        self.assertEqual([p.message_id for p in peer.pspeer_service.fetch(0, 'T1')], ['eligible'])
        self.assertEqual(hub.deliveries, [])
        self.assertEqual(len(hub.transmissions), 8)  # includes one live push
        for operation in ('SUBSCRIBE', 'PUBLISH', 'FETCH', 'DELIVER'):
            self.assertIn('operation=' + operation, self.logs)
        self.assertIn('node=1 source=0 destination=2 next=2 hops=2', self.logs)
        self.assertIn('node=1 source=2 destination=0 next=0 hops=2', self.logs)

    def test_no_peer_selected_does_not_send(self):
        client, hub, peer = self.run_network(selected=None)
        self.assertFalse(any(client.results))
        self.assertEqual(client.transmissions, [])

    def test_non_peer_ignores_requests(self):
        client, hub, destination = self.run_network(peer=False)
        self.assertTrue(all(client.results))
        self.assertEqual(client.deliveries, [])
        self.assertEqual(destination.transmissions, [])

    def test_lost_subscription_returns_empty_fetch_without_retry(self):
        client, hub, peer = self.run_network(early=True)
        self.assertFalse(client.results[0])
        self.assertEqual([m.publications for m in client.deliveries], [(), ()])

    def test_mismatched_identity_and_sync_are_ignored(self):
        client, hub, peer = self.run_network(invalid=True)
        self.assertEqual(peer.pspeer_service.fetch(99, 'T1'), ())
        self.assertEqual(len(client.deliveries), 2)
        self.assertEqual(len(peer.transmissions), 3)  # two FETCH replies and one push

    def test_factory_dispatch_overrides_transport_despite_peer_mro(self):
        for cls in (make_core_hub('swcore', pubsub=True),
                    make_core_rim(0, 'swcore', pubsub=True, pspeer=True)):
            self.assertIs(cls.handle_pubsub, PubSubAdapterMixin.handle_pubsub)
        self.assertFalse(issubclass(make_core_hub('swcore'), PubSubAdapterMixin))

    def test_client_rejects_invalid_peer_and_foreign_publication(self):
        client, _, _ = self.run_network(selected=None)
        for value in (-1, True, '2'):
            with self.assertRaises(ValueError):
                client.select_pspeer(value)
        with self.assertRaises(ValueError):
            client.publish_pubsub(Publication('foreign', 'T1', 99, Region.N, 0, {}))


if __name__ == '__main__':
    unittest.main()

