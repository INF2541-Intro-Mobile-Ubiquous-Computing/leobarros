"""Live fan-out through the core and SwCore's connected-satellite route table."""
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
from src.uav import make_satellite
import test_pubsub_transport as transport_tests


class PubSubPushTests(unittest.TestCase):
    setUp = transport_tests.PubSubTransportTests.setUp

    def run_network(self, subscribers=(4, 5, 6), filtered=(), disconnect=False,
                    duplicate=False, lose_delivery=False):
        positions = [(0, 0, 0), (50, 0, 0), (25, 25, 0), (25, 0, 0),
                     (0, 10, 0), (50, 10, 0), (50, -10, 0)]
        publication = Publication('live', 'T1', 0, 'N', 0.6, {'sample': [17]})

        class Core(PubSubAdapterMixin, transport_tests.test_protocol(0, 0.9, False)):
            def initialize(self):
                super().initialize()
                self.deliveries = []
                node = self.provider.get_id()
                if node in subscribers:
                    self.provider.schedule_timer('subscribe', 0.3)
                if node == 0:
                    self.provider.schedule_timer('publish', 0.6)
                    self.provider.schedule_timer('publish', 0.7)

            def handle_timer(self, timer):
                node = self.provider.get_id()
                if timer == 'beacon':
                    self.provider.send_communication_command(BroadcastMessageCommand(json.dumps({
                        'msg_type': 'core_beacon', 'sender_id': node,
                        'role': 'hub' if node == 3 else 'rim', 'position': positions[node],
                    })))
                elif timer == 'subscribe':
                    self.select_pspeer({4: 0, 5: 1}[node])
                    self.subscribe_pubsub('T1', {'S'} if node in filtered else {'N'})
                elif timer == 'publish':
                    self.select_pspeer(0)
                    self.publish_pubsub(publication)

            def on_pubsub_delivery(self, message):
                self.deliveries.append(message)

        class Peer(PSPeerMixin, Core):
            pspeer_slot = 0

        class StaticSatellite(IProtocol):
            def initialize(self):
                self._state = ST_EXCHANGE
                self._ack_node = 1
                self.deliveries = []
                self.provider.schedule_timer('connect', 0.15)
                if 6 in subscribers:
                    self.provider.schedule_timer('subscribe', 0.3)
                if disconnect:
                    self.provider.schedule_timer('disconnect', 0.5)

            def handle_timer(self, timer):
                if timer in ('connect', 'disconnect'):
                    self.provider.send_communication_command(SendMessageCommand(json.dumps({
                        'msg_type': 'dock_' + timer, 'sender_id': 6, 'face': 'N',
                    }), 1))
                    if timer == 'disconnect':
                        self._state = ST_COLLECT_OUT
                        self._ack_node = None
                elif timer == 'subscribe':
                    self.select_pspeer(2)
                    self.subscribe_pubsub('T1', {'S'} if 6 in filtered else {'N'})

            def handle_packet(self, message):
                pass

            def handle_telemetry(self, telemetry):
                pass

            def finish(self):
                pass

        class Satellite(PubSubSatelliteMixin, StaticSatellite):
            def on_pubsub_delivery(self, message):
                self.deliveries.append(message)

        class Radio(PubSubCommunicationHandler):
            def __init__(self):
                super().__init__(CommunicationMedium(transmission_range=30))
                self.pushes = []

            def handle_command(self, command, sender, medium=None):
                packet = json.loads(command.message)
                if packet.get('payload', {}).get('is_push'):
                    if packet['source_id'] == sender.id:
                        self.pushes.append((sender.id, packet['destination']))
                        if duplicate:
                            copied = dict(packet, transport_id=packet['transport_id'] + ':duplicate')
                            super().handle_command(SendMessageCommand(json.dumps(copied), command.destination),
                                                   sender, medium)
                    if lose_delivery:
                        return
                return super().handle_command(command, sender, medium)

        builder = SimulationBuilder(SimulationConfiguration(duration=0.9))
        for index, position in enumerate(positions):
            builder.add_node(Peer if index < 3 else Satellite if index == 6 else Core, position)
        radio = Radio()
        builder.add_handler(TimerHandler())
        builder.add_handler(radio)
        simulation = builder.build()
        logging.getLogger().setLevel(logging.CRITICAL)
        simulation.start_simulation()
        return [simulation.get_node(i).protocol_encapsulator.protocol for i in range(7)], radio, publication

    def test_tf01_single_eligible_subscriber(self):
        nodes, radio, item = self.run_network(subscribers=(4,))
        self.assertEqual(nodes[4].deliveries[0].publications, (item,))
        self.assertTrue(nodes[4].deliveries[0].is_push)
        self.assertEqual(radio.pushes, [(0, 4)])
        self.assertEqual(nodes[5].deliveries + nodes[6].deliveries, [])

    def test_tf02_multiple_subscribers_each_owned_by_one_peer(self):
        nodes, radio, item = self.run_network()
        self.assertCountEqual(radio.pushes, [(0, 4), (1, 5), (2, 6)])
        for node in nodes[4:]:
            self.assertEqual(len(node.deliveries), 1)
            self.assertEqual(node.deliveries[0].publications, (item,))
        self.assertEqual(nodes[0].deliveries, [])  # publisher never receives recipient lists
        self.assertEqual(nodes[2]._rt[6]['state'], 'hop')
        self.assertEqual(nodes[1]._rt[6]['state'], 'direct')
        self.assertTrue(any(p.get('destination') == 6 and p.get('hops') == 3
                            for p, _ in nodes[1].transmissions))

    def test_tf03_incompatible_filters_produce_no_delivery(self):
        nodes, radio, _ = self.run_network(filtered=(4, 5, 6))
        self.assertEqual(radio.pushes, [])
        self.assertTrue(all(not n.deliveries for n in nodes))

    def test_duplicate_push_with_new_transport_id_is_suppressed_at_client(self):
        nodes, radio, _ = self.run_network(duplicate=True)
        self.assertEqual([len(n.deliveries) for n in nodes[4:]], [1, 1, 1])
        self.assertEqual(len(radio.pushes), 3)

    def test_disconnected_satellite_not_sent_or_marked_consumed(self):
        nodes, radio, item = self.run_network(disconnect=True)
        self.assertEqual(nodes[6].deliveries, [])
        self.assertNotIn((2, 6), radio.pushes)
        self.assertEqual(nodes[2].pspeer_service.fetch(6, 'T1'), (item,))
        self.assertEqual(len(nodes[2]._core_buffer), 1)
        self.assertEqual(list(nodes[2]._pubsub_delivery_state.values()), ['pending'])
        self.assertEqual(nodes[2]._buffered_for(6), [])  # excluded from legacy dock delivery
        self.assertFalse(nodes[6].fetch_pubsub('T1'))

    def test_send_loss_does_not_mark_consumption_or_retry(self):
        nodes, radio, item = self.run_network(lose_delivery=True)
        self.assertEqual(len(radio.pushes), 3)
        self.assertTrue(all(not n.deliveries for n in nodes))
        for peer, subscriber in zip(nodes[:3], (4, 5, 6)):
            self.assertEqual(peer.pspeer_service.fetch(subscriber, 'T1'), (item,))

    def test_satellite_factory_opt_in_preserves_original_mobility_callbacks(self):
        plain = make_satellite('N', swcore=True)
        enabled = make_satellite('N', swcore=True, pubsub=True)
        self.assertFalse(issubclass(plain, PubSubSatelliteMixin))
        self.assertTrue(issubclass(enabled, PubSubSatelliteMixin))
        for method in ('handle_telemetry', '_depart'):
            self.assertEqual(getattr(plain, method).__qualname__, getattr(enabled, method).__qualname__)
        with self.assertRaises(ValueError):
            make_satellite('N', pubsub=True)
