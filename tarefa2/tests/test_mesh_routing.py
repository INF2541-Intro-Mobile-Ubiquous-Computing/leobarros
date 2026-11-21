"""Distributed discovery and forwarding through ordinary simulated radio."""
import json
import logging
import unittest
from unittest.mock import Mock

from gradysim.protocol.interface import IProtocol
from gradysim.protocol.messages.communication import BroadcastMessageCommand
from gradysim.simulator.handler.communication import CommunicationHandler, CommunicationMedium
from gradysim.simulator.handler.timer import TimerHandler
from gradysim.simulator.simulation import SimulationBuilder, SimulationConfiguration
from src.neighbor_mixin import NeighborMixin
from src.pubsub.adapter import PubSubAdapterMixin
from src.pubsub.mesh_routing import MeshRoutingMixin
from src.pubsub.models import FetchEnvelope
from src.pubsub.transport import PubSubTransportMixin
from src.swcore_mixin import SWCoreMixin
from src.uav import make_satellite
from src.satellite import ST_WAIT_ALIGN, ST_EXCHANGE
import test_pubsub_transport as transport_tests


class Base(IProtocol):
    def initialize(self):
        self._core_buffer = {}
        self.is_pspeer = self.provider.get_id() in (1, 2, 4)
        self.received = []
        self.provider.schedule_timer('beacon', 0.05)
        self.provider.schedule_timer('request', 1.2)

    def handle_timer(self, timer):
        if timer == 'beacon':
            self.provider.send_communication_command(BroadcastMessageCommand(json.dumps(dict(
                msg_type='core_beacon', sender_id=self.provider.get_id(), role='rim'))))
            self.provider.schedule_timer(timer, self.provider.current_time() + 0.1)
        elif timer == 'request' and self.provider.get_id() == 0:
            self.send_pubsub(4, FetchEnvelope(0, 0, 'T1'))

    def handle_packet(self, message):
        pass

    def handle_telemetry(self, telemetry):
        pass

    def finish(self):
        pass


class Core(PubSubAdapterMixin, MeshRoutingMixin, PubSubTransportMixin,
           NeighborMixin, SWCoreMixin, Base):
    def handle_pubsub(self, message, source_id):
        self.received.append((source_id, message))


class MeshRoutingTests(unittest.TestCase):
    setUp = transport_tests.PubSubTransportTests.setUp

    def network(self):
        builder = SimulationBuilder(SimulationConfiguration(duration=1.5))
        for position in ((0, 0, 0), (25, 0, 0), (0, 25, 0), (25, 25, 0), (50, 25, 0)):
            builder.add_node(Core, position)
        builder.add_handler(TimerHandler())
        builder.add_handler(CommunicationHandler(CommunicationMedium(transmission_range=26)))
        sim = builder.build()
        logging.getLogger().setLevel(logging.CRITICAL)
        sim.start_simulation()
        return [sim.get_node(n).protocol_encapsulator.protocol for n in range(5)]

    def test_radio_discovers_nearest_peer_and_routes_without_hub(self):
        nodes = self.network()
        self.assertEqual([n.selected_pspeer for n in nodes], [1, 1, 2, 1, 4])
        self.assertEqual(nodes[0]._mesh_rt[4]['path'], (0, 1, 3, 4))
        self.assertEqual(nodes[4].received, [(0, FetchEnvelope(0, 0, 'T1'))])
        self.assertTrue(all(not n.received for n in nodes[:4]))
        self.assertIsNot(nodes[0]._link_state, nodes[1]._link_state)

    def test_alternate_path_and_satellite_disconnect_versions(self):
        nodes = self.network()
        node = nodes[0]
        node._remember_satellite(dict(sat=99, state='reachable', ver=[1, 3, 1]))
        node._rebuild_routes()
        self.assertEqual(node._rt[99]['path'], (0, 1, 3, 99))
        # Remove a link in the local advertised graph, not a simulator oracle.
        node._link_state[0]['neighbors'].remove(1)
        node._rebuild_routes()
        self.assertEqual(node.selected_pspeer, 2)
        self.assertEqual(node._rt[99]['path'], (0, 2, 3, 99))
        node._remember_satellite(dict(sat=99, state='unreachable', ver=[2, 3, 2]))
        node._remember_satellite(dict(sat=99, state='reachable', ver=[1, 3, 1]))
        node._rebuild_routes()
        self.assertEqual(node._rt[99]['state'], 'unreachable')
        node._remember_satellite(dict(sat=99, state='reachable', ver=[3, 4, 1]))
        node._rebuild_routes()
        self.assertEqual(node._rt[99]['path'], (0, 2, 3, 4, 99))

    def test_expired_advertisement_withdraws_route_and_retains_delivery(self):
        node = self.network()[0]
        node._remember_satellite(dict(sat=99, state='reachable', ver=[1, 3, 1]))
        node._link_state[3]['time'] = -10
        node._rebuild_routes()
        self.assertNotIn(4, node._mesh_rt)
        self.assertEqual(node._rt[99]['state'], 'unreachable')
        packet = dict(destination=99, source_id=0, transport_id='pending', hops=0,
                      payload=dict(operation='DELIVER'))
        self.assertFalse(node._forward_pubsub(packet))
        core_packet = dict(packet, destination=4, transport_id='core-pending')
        self.assertFalse(node._forward_pubsub(core_packet))
        self.assertIn('pubsub-buffer:pending', node._core_buffer)
        node._link_state[3]['time'] = node.provider.current_time()
        node._rebuild_routes()
        self.assertNotIn('pubsub-buffer:pending', node._core_buffer)
        self.assertNotIn('pubsub-buffer:core-pending', node._core_buffer)

    def test_contact_selects_advertised_peer_only_for_accepted_ack(self):
        node = make_satellite('N', swcore=True, pubsub=True)()
        node.provider = Mock()
        node.provider.get_id.return_value = 99
        node.provider.current_time.return_value = 1.0
        node.initialize()
        node._state = ST_WAIT_ALIGN
        node.handle_packet(json.dumps(dict(msg_type='dock_ack', face='S', sender_id=3, pspeer_id=2)))
        self.assertIsNone(node.selected_pspeer)
        node.handle_packet(json.dumps(dict(msg_type='dock_ack', face='N', sender_id=3, pspeer_id=2)))
        self.assertEqual((node.selected_pspeer, node._state), (2, ST_EXCHANGE))
        node.handle_packet(json.dumps(dict(msg_type='dock_ack', face='N', sender_id=4, pspeer_id=4)))
        self.assertEqual(node.selected_pspeer, 2)
