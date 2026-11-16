"""Seeded core publication timers and TF04 through real simulated radio."""
import json
import logging
import random
import unittest
from unittest.mock import Mock, patch

from gradysim.protocol.messages.communication import BroadcastMessageCommand
from gradysim.simulator.handler.communication import CommunicationMedium
from gradysim.simulator.handler.timer import TimerHandler
from gradysim.simulator.simulation import SimulationBuilder, SimulationConfiguration

from src.pubsub.adapter import PubSubAdapterMixin
from src.pubsub.core_publications import CorePublicationMixin
from src.pubsub.pspeer_mixin import PSPeerMixin
from src.pubsub.radio import PubSubCommunicationHandler
from src.uav import make_core_hub, make_core_rim, make_satellite
import test_pubsub_transport as transport_tests


class CorePublicationTests(unittest.TestCase):
    setUp = transport_tests.PubSubTransportTests.setUp

    def make_generator(self, node, seed=2056, interval=5, peer=False):
        class Base:
            def initialize(self):
                self.selected_pspeer = None
                self.generated = []
                self.other_timers = []

            def select_pspeer(self, destination):
                self.selected_pspeer = destination

            def publish_pubsub(self, publication):
                self.generated.append(publication)
                return False

            def handle_timer(self, timer):
                self.other_timers.append(timer)

        class Generator(CorePublicationMixin, Base):
            initial_core_pspeer_id = 7
            is_pspeer = peer

        generator = Generator()
        generator.provider = Mock()
        generator.provider.get_id.return_value = node
        generator.provider.current_time.return_value = 0
        with (patch('src.pubsub.core_publications.PUBSUB_SEED', seed),
              patch('src.pubsub.core_publications.PUBSUB_PUBLICATION_INTERVAL', interval)):
            generator.initialize()
        return generator

    def fire(self, generator, count=10):
        for index in range(count):
            generator.provider.current_time.return_value = (index + 1) * generator._core_publication_interval
            generator.handle_timer(generator.core_publication_timer)
        return generator.generated

    def test_seeded_streams_reproduce_independent_of_execution_order_and_global_rng(self):
        state = random.getstate()
        a, b = self.make_generator(1), self.make_generator(2)
        first_a, first_b = self.fire(a), self.fire(b)
        b2, a2 = self.make_generator(2), self.make_generator(1)
        self.assertEqual(self.fire(b2), first_b)
        self.assertEqual(self.fire(a2), first_a)
        self.assertNotEqual(first_a, self.fire(self.make_generator(1, seed=10)))
        self.assertNotEqual([p.payload for p in first_a], [p.payload for p in first_b])
        self.assertEqual(random.getstate(), state)

    def test_interval_ids_region_and_peer_choice_with_failed_submission(self):
        generator = self.make_generator(3, interval=2)
        generator.provider.schedule_timer.assert_called_once_with('pubsub_core_publish', 2)
        values = self.fire(generator, 3)
        self.assertEqual([p.message_id for p in values], ['core:3:1', 'core:3:2', 'core:3:3'])
        self.assertEqual([p.created_at for p in values], [2, 4, 6])
        self.assertTrue(all(p.origin_id == 3 and p.origin_region.value == 'C' for p in values))
        generator.provider.schedule_timer.assert_called_with('pubsub_core_publish', 8)
        self.assertEqual(generator.selected_pspeer, 7)
        self.assertEqual(self.make_generator(3, peer=True).selected_pspeer, 3)
        generator.handle_timer('movement')
        self.assertEqual(generator.other_timers, ['movement'])

    def test_invalid_intervals_fail_before_scheduling(self):
        for interval in (0, -1, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                self.make_generator(0, interval=interval)

    def test_generation_is_only_in_opt_in_core_factories(self):
        for factory in (lambda enabled: make_core_hub('swcore', pubsub=enabled),
                        lambda enabled: make_core_rim(0, 'swcore', pubsub=enabled)):
            self.assertFalse(issubclass(factory(False), CorePublicationMixin))
            self.assertTrue(issubclass(factory(True), CorePublicationMixin))
        self.assertFalse(issubclass(make_satellite('N', swcore=True, pubsub=True), CorePublicationMixin))

    def run_network(self, accepted_region):
        class Client(PubSubAdapterMixin, transport_tests.test_protocol(2, 0.9, False)):
            def initialize(self):
                super().initialize()
                self.deliveries = []
                self.provider.schedule_timer('beacon', 0.01)
                if self.provider.get_id() == 0:
                    # GrADyS checks duration after an event; make the first event
                    # beyond the horizon inert, before the next publication.
                    self.provider.schedule_timer('end_test', 1.06)
                if self.provider.get_id() == 3:
                    self.provider.schedule_timer('subscribe', 0.075)

            def handle_timer(self, timer):
                if timer == 'beacon':
                    node = self.provider.get_id()
                    self.provider.send_communication_command(BroadcastMessageCommand(json.dumps({
                        'msg_type': 'core_beacon', 'sender_id': node,
                        'role': 'hub' if node == 1 else 'rim', 'position': [0, 0, 0]})))
                    self.provider.schedule_timer('beacon', self.provider.current_time() + 0.3)
                elif timer == 'subscribe':
                    self.select_pspeer(2)
                    for topic in ('T1', 'T2'):
                        self.subscribe_pubsub(topic, {accepted_region})

            def on_pubsub_delivery(self, message):
                self.deliveries.extend(message.publications)

        class Publisher(CorePublicationMixin, Client):
            initial_core_pspeer_id = 2

            def publish_pubsub(self, publication):
                self.generated.append(publication)
                return super().publish_pubsub(publication)

            def initialize(self):
                self.generated = []
                super().initialize()

        class Peer(PSPeerMixin, Client):
            pspeer_slot = 0

        builder = SimulationBuilder(SimulationConfiguration(duration=1.05))
        for cls, position in [(Publisher, (0, 0, 0)), (Client, (25, 0, 0)),
                              (Peer, (50, 0, 0)), (Client, (50, 10, 0))]:
            builder.add_node(cls, position)
        builder.add_handler(TimerHandler())
        builder.add_handler(PubSubCommunicationHandler(CommunicationMedium(transmission_range=30)))
        with patch('src.pubsub.core_publications.PUBSUB_PUBLICATION_INTERVAL', 0.1):
            simulation = builder.build()
            logging.getLogger().setLevel(logging.CRITICAL)
            simulation.start_simulation()
        return [simulation.get_node(i).protocol_encapsulator.protocol for i in range(4)]

    def test_tf04_core_publications_reach_subscriber_accepting_region_c(self):
        publisher, hub, peer, subscriber = self.run_network('C')
        self.assertEqual(len(publisher.generated), 10)
        self.assertEqual(subscriber.deliveries, publisher.generated)
        self.assertEqual({p.topic for p in subscriber.deliveries}, {'T1', 'T2'})
        self.assertTrue(all(p.origin_region.value == 'C' for p in subscriber.deliveries))
        self.assertTrue(any(p['payload']['operation'] == 'PUBLISH' and p['hops'] == 2
                            for p, _ in hub.transmissions))

    def test_core_publications_are_stored_but_not_delivered_to_incompatible_filter(self):
        publisher, _, peer, subscriber = self.run_network('N')
        self.assertEqual(subscriber.deliveries, [])
        self.assertEqual(sum(len(peer.pspeer_service._topics.get_history(t)) for t in ('T1', 'T2')), 10)
