"""Core transport tests using real simulated radio, timers and beacons."""
import json
import logging
import unittest
from unittest.mock import patch

from gradysim.protocol.interface import IProtocol
from gradysim.protocol.messages.communication import BroadcastMessageCommand
from gradysim.simulator.handler.communication import CommunicationHandler, CommunicationMedium
from gradysim.simulator.handler.timer import TimerHandler
from gradysim.simulator.simulation import SimulationBuilder, SimulationConfiguration

from src.neighbor_mixin import NeighborMixin
from src.pubsub.models import FetchEnvelope
from src.pubsub.transport import PubSubTransportMixin
from src.swcore_mixin import SWCoreMixin
from src.uav import make_core_hub, make_core_rim


def test_protocol(destination, send_at, repeat):
    class StaticCore(IProtocol):
        def initialize(self):
            self._core_buffer = {}
            self.received = []
            self.transmissions = []
            self.send_result = None
            self.provider.schedule_timer('beacon', 0.1)
            if self.provider.get_id() == 0:
                self.provider.schedule_timer('send_test', send_at)

        def handle_timer(self, timer):
            if timer == 'beacon':
                node = self.provider.get_id()
                self.provider.send_communication_command(BroadcastMessageCommand(json.dumps({
                    'msg_type': 'core_beacon', 'sender_id': node,
                    'role': 'hub' if node == 1 else 'rim', 'position': [node * 25, 0, 0],
                })))
            elif timer == 'send_test':
                self.send_result = self.send_pubsub(destination, FetchEnvelope(0, 0, 'T1'))
                if repeat and self.transmissions:
                    packet, target = self.transmissions[0]
                    self._send(dict(packet), target)

        def handle_packet(self, message):
            pass

        def handle_telemetry(self, telemetry):
            pass

        def finish(self):
            pass

    class Core(PubSubTransportMixin, NeighborMixin, SWCoreMixin, StaticCore):
        def _send(self, packet, target):
            self.transmissions.append((dict(packet), target))
            super()._send(packet, target)

        def handle_pubsub(self, message, source_id):
            self.received.append((source_id, message))

    return Core


class PubSubTransportTests(unittest.TestCase):
    def setUp(self):
        root = logging.getLogger()
        handlers, level = root.handlers[:], root.level

        def restore():
            for handler in root.handlers[:]:
                if handler not in handlers:
                    root.removeHandler(handler)
                    handler.close()
            root.handlers = handlers
            root.setLevel(level)

        self.addCleanup(restore)

    def run_network(self, destination=2, send_at=0.5, repeat=False):
        # Endpoints are 50 m apart; the 30 m radio forces two hops via node 1.
        builder = SimulationBuilder(SimulationConfiguration(duration=0.8))
        protocol = test_protocol(destination, send_at, repeat)
        for x in (0, 25, 50):
            builder.add_node(protocol, (x, 0, 0))
        builder.add_handler(TimerHandler())
        builder.add_handler(CommunicationHandler(CommunicationMedium(transmission_range=30)))
        simulation = builder.build()
        logging.getLogger().setLevel(logging.CRITICAL)
        simulation.start_simulation()
        return [simulation.get_node(n).protocol_encapsulator.protocol for n in range(3)]

    def test_two_hop_delivery_uses_hub_and_preserves_application_sender(self):
        source, hub, destination = self.run_network()
        self.assertTrue(source.send_result)
        self.assertEqual(source.received, [])
        self.assertEqual(hub.received, [])
        self.assertEqual(destination.received, [(0, FetchEnvelope(0, 0, 'T1'))])
        self.assertEqual(source.transmissions[0][1], 1)
        self.assertEqual(hub.transmissions[0][1], 2)
        self.assertEqual(hub.transmissions[0][0]['hops'], 2)
        self.assertEqual(destination.transmissions, [])

    def test_direct_neighbor_delivery_takes_one_hop(self):
        source, hub, other = self.run_network(destination=1)
        self.assertEqual(hub.received, [(0, FetchEnvelope(0, 0, 'T1'))])
        self.assertEqual(source.transmissions[0][0]['hops'], 1)
        self.assertEqual(hub.transmissions, [])
        self.assertEqual(other.received, [])

    def test_no_neighbor_discovery_returns_false_without_sending(self):
        source, hub, destination = self.run_network(send_at=0)
        self.assertFalse(source.send_result)
        self.assertEqual(source.transmissions, [])
        self.assertEqual(hub.transmissions, [])
        self.assertEqual(destination.received, [])

    def test_local_destination_dispatches_without_self_unicast(self):
        source, hub, destination = self.run_network(destination=0)
        self.assertTrue(source.send_result)
        self.assertEqual(source.received, [(0, FetchEnvelope(0, 0, 'T1'))])
        self.assertEqual(source.transmissions, [])

    def test_duplicate_radio_packet_is_delivered_only_once(self):
        source, hub, destination = self.run_network(repeat=True)
        self.assertEqual(len(source.transmissions), 2)
        self.assertEqual(len(hub.transmissions), 1)
        self.assertEqual(len(destination.received), 1)

    def test_hop_limit_prevents_forwarding_beyond_limit(self):
        with patch('src.pubsub.transport.PUBSUB_TRANSPORT_MAX_HOPS', 1):
            source, hub, destination = self.run_network()
        self.assertTrue(source.send_result)  # submission is not a delivery ACK
        self.assertEqual(hub.transmissions, [])
        self.assertEqual(destination.received, [])

    def test_unknown_destination_does_not_loop_back_from_hub(self):
        source, hub, destination = self.run_network(destination=99)
        self.assertTrue(source.send_result)
        self.assertEqual(hub.transmissions, [])
        self.assertEqual(destination.received, [])

    def test_factory_transport_is_opt_in_and_requires_swcore(self):
        self.assertFalse(issubclass(make_core_hub('swcore'), PubSubTransportMixin))
        self.assertFalse(issubclass(make_core_rim(0, 'swcore'), PubSubTransportMixin))
        self.assertTrue(issubclass(make_core_hub('swcore', pubsub=True), PubSubTransportMixin))
        self.assertTrue(issubclass(make_core_rim(0, 'swcore', pubsub=True), PubSubTransportMixin))
        with self.assertRaises(ValueError):
            make_core_hub('flooding', pubsub=True)


if __name__ == '__main__':
    unittest.main()
