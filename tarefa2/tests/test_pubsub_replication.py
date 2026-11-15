"""Publish through A and fetch through B/C using simulated radio throughout."""
from dataclasses import replace
import json
import logging
import unittest

from gradysim.protocol.messages.communication import BroadcastMessageCommand
from gradysim.simulator.handler.communication import CommunicationMedium
from gradysim.simulator.handler.timer import TimerHandler
from gradysim.simulator.simulation import SimulationBuilder, SimulationConfiguration

from src.pubsub.adapter import PubSubAdapterMixin
from src.pubsub.models import Publication
from src.pubsub.pspeer_mixin import PSPeerMixin
from src.pubsub.radio import PubSubCommunicationHandler, ReplicateBroadcastCommand
import test_pubsub_transport as transport_tests


class PubSubReplicationTests(unittest.TestCase):
    setUp = transport_tests.PubSubTransportTests.setUp

    def run_network(self, duplicate=False, second_ingress=False, lost_nodes=(), delay=0):
        positions = [(0, 0, 0), (50, 0, 0), (25, 25, 0), (25, 0, 0), (10, 0, 0)]
        items = (Publication('north', 'T1', 4, 'N', 0.3, {'value': [1]}),
                 Publication('south', 'T1', 4, 'S', 0.3, {'value': [2]}))

        class Core(PubSubAdapterMixin, transport_tests.test_protocol(0, 0.3, False)):
            def initialize(self):
                super().initialize()
                self.deliveries = []
                self.replica_packets = []
                if self.provider.get_id() == 4:
                    for timer, when in [('subscribe', 0.2), ('publish', 0.3), ('repeat', 0.4),
                                        ('fetch_b', 0.6), ('fetch_c', 0.8), ('fetch_a', 1.0)]:
                        self.provider.schedule_timer(timer, when)

            def handle_timer(self, timer):
                node = self.provider.get_id()
                if timer == 'beacon':
                    self.provider.send_communication_command(BroadcastMessageCommand(json.dumps({
                        'msg_type': 'core_beacon', 'sender_id': node,
                        'role': 'hub' if node == 3 else 'rim', 'position': positions[node],
                    })))
                elif timer == 'subscribe':
                    self.select_pspeer(0)
                    self.subscribe_pubsub('T1', {'N'})
                elif timer == 'publish':
                    for item in items:
                        self.publish_pubsub(item)
                elif timer == 'repeat':
                    if second_ingress:
                        self.select_pspeer(1)
                    # Same ID with a different body must not replace the first copy.
                    self.publish_pubsub(replace(items[0], payload={'value': ['changed']}))
                elif timer.startswith('fetch_'):
                    self.select_pspeer({'fetch_b': 1, 'fetch_c': 2, 'fetch_a': 0}[timer])
                    self.fetch_pubsub('T1')

            def handle_packet(self, message):
                if json.loads(message).get('msg_type') == 'pubsub_replicate':
                    self.replica_packets.append(json.loads(message))
                super().handle_packet(message)

            def on_pubsub_delivery(self, message):
                if not message.is_push:  # keep testing explicit queries independently of push
                    self.deliveries.append(message)

        class Peer(PSPeerMixin, Core):
            pspeer_slot = 0

        class Radio(PubSubCommunicationHandler):
            def __init__(self):
                super().__init__(CommunicationMedium(transmission_range=30))
                self.replicates = []

            def handle_command(self, command, sender, medium=None):
                if isinstance(command, ReplicateBroadcastCommand):
                    self.replicates.append((sender.id, json.loads(command.message)))
                    medium = replace(self.default_medium, delay=delay)
                    if duplicate:
                        super().handle_command(command, sender, medium)
                return super().handle_command(command, sender, medium)

            def _transmit_message(self, message, source, destination, medium):
                if (json.loads(message).get('msg_type') == 'pubsub_replicate'
                        and destination.node.id in lost_nodes):
                    medium = replace(medium, failure_rate=1)
                return super()._transmit_message(message, source, destination, medium)

        builder = SimulationBuilder(SimulationConfiguration(duration=1.2))
        for node, position in enumerate(positions):
            builder.add_node(Peer if node < 3 else Core, position)
        radio = Radio()
        builder.add_handler(TimerHandler())
        builder.add_handler(radio)
        simulation = builder.build()
        logging.getLogger().setLevel(logging.CRITICAL)
        simulation.start_simulation()
        nodes = [simulation.get_node(n).protocol_encapsulator.protocol for n in range(5)]
        return nodes, radio, items

    def test_publish_in_a_fetch_in_b_c_preserves_origin_content_and_filter(self):
        nodes, radio, items = self.run_network()
        self.assertEqual([m.sender_id for m in nodes[4].deliveries], [1, 2, 0])
        self.assertEqual([m.publications for m in nodes[4].deliveries], [(items[0],)] * 3)
        self.assertEqual([sender for sender, _ in radio.replicates], [0, 0])
        for peer in nodes[:3]:
            self.assertEqual(peer.pspeer_service.fetch(4, 'T1'), (items[0],))
            # Replication stores even publications excluded by the current filter.
            self.assertEqual(peer.pspeer_service._topics.get_history('T1'), items)
        for non_peer in nodes[3:]:
            self.assertEqual(len(non_peer.replica_packets), 2)
            self.assertFalse(hasattr(non_peer, 'pspeer_service'))
        self.assertTrue(any(packet['payload']['operation'] == 'FETCH' and packet['hops'] == 2
                            for packet, _ in nodes[3].transmissions))

    def test_duplicate_radio_replicas_do_not_duplicate_history_or_rebroadcast(self):
        nodes, radio, items = self.run_network(duplicate=True)
        self.assertEqual(len(radio.replicates), 2)
        self.assertEqual(len(nodes[1].replica_packets), 4)
        self.assertEqual(nodes[1].pspeer_service._topics.get_history('T1'), items)
        self.assertEqual([m.publications for m in nodes[4].deliveries], [(items[0],)] * 3)

    def test_repeated_publish_at_another_peer_keeps_first_copy_without_new_broadcast(self):
        nodes, radio, items = self.run_network(second_ingress=True)
        self.assertEqual([sender for sender, _ in radio.replicates], [0, 0])
        self.assertEqual([m.publications for m in nodes[4].deliveries], [(items[0],)] * 3)

    def test_total_replication_loss_is_not_repaired_by_identical_publish(self):
        nodes, radio, items = self.run_network(lost_nodes=(1, 2, 3, 4))
        self.assertEqual(len(radio.replicates), 2)
        self.assertEqual([m.publications for m in nodes[4].deliveries], [(), (), (items[0],)])
        self.assertEqual(nodes[1].replica_packets, [])

    def test_partial_loss_does_not_trigger_relay_from_other_replica(self):
        nodes, radio, items = self.run_network(lost_nodes=(2,))
        self.assertEqual([sender for sender, _ in radio.replicates], [0, 0])
        self.assertEqual([m.publications for m in nodes[4].deliveries], [(items[0],), (), (items[0],)])

    def test_replication_preserves_medium_delay(self):
        nodes, radio, items = self.run_network(delay=0.4)
        self.assertEqual([m.publications for m in nodes[4].deliveries], [(), (items[0],), (items[0],)])
