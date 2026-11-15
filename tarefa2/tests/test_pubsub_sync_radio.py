"""Three real radio replicas beyond ordinary range, with losses and duplicates."""
import json
import logging
import unittest
from unittest.mock import patch

from gradysim.protocol.messages.communication import BroadcastMessageCommand
from gradysim.simulator.handler.communication import CommunicationMedium
from gradysim.simulator.handler.timer import TimerHandler
from gradysim.simulator.simulation import SimulationBuilder, SimulationConfiguration

from src.pubsub.adapter import PubSubAdapterMixin
from src.pubsub.models import Publication
from src.pubsub.pspeer_mixin import PSPeerMixin
from src.pubsub.radio import PubSubCommunicationHandler, SyncBroadcastCommand
import test_pubsub_transport as transport_tests


class PubSubSyncRadioTests(unittest.TestCase):
    setUp = transport_tests.PubSubTransportTests.setUp

    def run_network(self, failure=0, duplicate=False, sync_range=60):
        class Core(PubSubAdapterMixin, transport_tests.test_protocol(0, 0.3, False)):
            def initialize(self):
                super().initialize()
                self.ordinary = []
                self.sync_received = 0
                if self.provider.get_id() == 0:
                    for timer, when in [('change', 0.3), ('change', 0.4), ('ordinary', 0.5)]:
                        self.provider.schedule_timer(timer, when)

            def handle_timer(self, timer):
                if timer == 'change':
                    self.select_pspeer(0)
                    self.subscribe_pubsub('T1', {'N'})
                elif timer == 'ordinary':
                    self.provider.send_communication_command(BroadcastMessageCommand(
                        json.dumps({'msg_type': 'ordinary_test'})))
                elif timer != 'send_test':
                    super().handle_timer(timer)

            def handle_packet(self, message):
                kind = json.loads(message).get('msg_type')
                if kind == 'ordinary_test':
                    self.ordinary.append(message)
                    return
                if kind == 'pubsub_sync':
                    self.sync_received += 1
                super().handle_packet(message)

        class Peer(PSPeerMixin, Core):
            pspeer_slot = 0

        class RecordingRadio(PubSubCommunicationHandler):
            def __init__(self):
                super().__init__(CommunicationMedium(transmission_range=30, failure_rate=failure))
                self.broadcasts = []

            def handle_command(self, command, sender, medium=None):
                if isinstance(command, SyncBroadcastCommand):
                    self.broadcasts.append((sender.id, command.message))
                    if duplicate:
                        super().handle_command(command, sender, medium)
                return super().handle_command(command, sender, medium)

        builder = SimulationBuilder(SimulationConfiguration(duration=0.8))
        # Peers 1/2 cannot hear peer 0 with the ordinary 30 m radio.
        for cls, position in [(Peer, (0, 0, 0)), (Peer, (50, 0, 0)),
                              (Peer, (25, 40, 0)), (Core, (25, 0, 0))]:
            builder.add_node(cls, position)
        radio = RecordingRadio()
        builder.add_handler(TimerHandler())
        builder.add_handler(radio)
        simulation = builder.build()
        logging.getLogger().setLevel(logging.CRITICAL)
        with patch('src.pubsub.radio.PUBSUB_SYNC_RANGE', sync_range):
            simulation.start_simulation()
        nodes = [simulation.get_node(i).protocol_encapsulator.protocol for i in range(4)]
        # Probe each independent store with the same local fixture; publications
        # are deliberately not replicated by stage 14.
        for node in nodes[:3]:
            node.pspeer_service.publish(Publication('probe', 'T1', 0, 'N', 0, {}))
        return nodes, radio

    def test_one_broadcast_reaches_three_replicas_and_non_peer_discards(self):
        nodes, radio = self.run_network()
        self.assertEqual(len(radio.broadcasts), 1)  # identical SUBSCRIBE sends no delta
        self.assertEqual([len(n.pspeer_service.fetch(0, 'T1')) for n in nodes[:3]], [1, 1, 1])
        self.assertEqual([n.sync_received for n in nodes], [0, 1, 1, 1])
        self.assertFalse(hasattr(nodes[3], 'pspeer_service'))
        self.assertEqual([len(n.ordinary) for n in nodes], [0, 0, 0, 1])
        self.assertTrue(all(not n.transmissions for n in nodes))

    def test_duplicate_radio_sync_is_idempotent_without_repropagation(self):
        nodes, radio = self.run_network(duplicate=True)
        self.assertEqual(len(radio.broadcasts), 1)
        self.assertEqual(nodes[1].sync_received, 2)
        self.assertEqual([len(n.pspeer_service.fetch(0, 'T1')) for n in nodes[:3]], [1, 1, 1])

    def test_total_loss_leaves_remote_replicas_stale_without_retry(self):
        nodes, radio = self.run_network(failure=1)
        self.assertEqual(len(radio.broadcasts), 1)
        self.assertEqual([len(n.pspeer_service.fetch(0, 'T1')) for n in nodes[:3]], [1, 0, 0])
        self.assertEqual([n.sync_received for n in nodes], [0, 0, 0, 0])

    def test_out_of_range_sync_is_not_relayed_by_nearby_core(self):
        nodes, radio = self.run_network(sync_range=30)
        self.assertEqual(len(radio.broadcasts), 1)
        self.assertEqual([n.sync_received for n in nodes], [0, 0, 0, 1])
        self.assertEqual([len(n.pspeer_service.fetch(0, 'T1')) for n in nodes[:3]], [1, 0, 0])
