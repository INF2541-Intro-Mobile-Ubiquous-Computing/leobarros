"""Sensor radio collection -> offline queue -> PUBLISH at a contact -> replicas."""
import json
import logging
import unittest
from unittest.mock import Mock, patch

from gradysim.protocol.messages.communication import BroadcastMessageCommand, SendMessageCommand
from gradysim.simulator.handler.communication import CommunicationMedium
from gradysim.simulator.handler.timer import TimerHandler
from gradysim.simulator.simulation import SimulationBuilder, SimulationConfiguration

from src import main
from src.pubsub.adapter import PubSubAdapterMixin
from src.pubsub.pspeer_mixin import PSPeerMixin
from src.pubsub.radio import PubSubCommunicationHandler
from src.pubsub.satellite_client import PubSubSatelliteMixin
from src.pubsub.sensor_publications import SensorPublicationMixin
from src.satellite import make_satellite_protocol, ST_COLLECT_OUT, ST_EXCHANGE
from src.uav import make_satellite
from utils.actor_templates.sensor_template import SensorProtocol
import test_pubsub_transport as transport_tests


class SensorPublicationTests(unittest.TestCase):
    setUp = transport_tests.PubSubTransportTests.setUp

    def run_network(self, face='N', no_peer=False, lose_publish=False):
        snapshots = []

        class SatelliteBase(make_satellite_protocol(face, swcore=True)):
            def initialize(self):
                self._state = ST_COLLECT_OUT
                self._ack_node = None
                self.packets = {}
                for timer, when in [('collect', 0.2), ('snapshot', 0.3), ('contact', 0.4),
                                    ('snapshot', 0.5), ('retry_contact', 0.6), ('contact', 0.8)]:
                    self.provider.schedule_timer(timer, when)

            def _start_exchange(self, ack_node_id):
                self._state = ST_EXCHANGE
                self._ack_node = ack_node_id
                self.provider.send_communication_command(SendMessageCommand(json.dumps({
                    'msg_type': 'dock_connect', 'sender_id': 0, 'face': face}), ack_node_id))

            def handle_timer(self, timer):
                if timer == 'collect':
                    self.provider.send_communication_command(BroadcastMessageCommand(
                        json.dumps({'sender_type': 1, 'sender_id': 0})))
                elif timer == 'snapshot':
                    snapshots.append((dict(self._pending_sensor_publications), dict(self.packets)))
                elif timer == 'retry_contact':
                    self.select_pspeer(1)
                    self._start_exchange(4)
                elif timer == 'contact':
                    self._start_exchange(4)

            def finish(self):
                pass

        class Satellite(SensorPublicationMixin, PubSubSatelliteMixin, SatelliteBase):
            sensor_origin_region = face
            initial_pspeer_id = None if no_peer else 1

        class Core(PubSubAdapterMixin, transport_tests.test_protocol(0, 0.9, False)):
            def handle_timer(self, timer):
                if timer == 'beacon':
                    node = self.provider.get_id()
                    self.provider.send_communication_command(BroadcastMessageCommand(json.dumps({
                        'msg_type': 'core_beacon', 'sender_id': node,
                        'role': 'hub' if node == 4 else 'rim', 'position': [25, 0, 0]})))

        class Peer(PSPeerMixin, Core):
            pspeer_slot = 0

        def sensor(logical_id):
            class Source(SensorProtocol):
                sensor_id = logical_id

                def initialize(self):
                    super().initialize()
                    self.handle_timer('gen')
                    self.handle_timer('gen')

                def finish(self):
                    pass
            return Source

        class Radio(PubSubCommunicationHandler):
            def __init__(self):
                super().__init__(CommunicationMedium(transmission_range=30))
                self.publishes = []

            def handle_command(self, command, sender, medium=None):
                packet = json.loads(command.message)
                if packet.get('payload', {}).get('operation') == 'PUBLISH' and sender.id == 0:
                    self.publishes.append(packet)
                    if lose_publish:
                        return
                return super().handle_command(command, sender, medium)

        builder = SimulationBuilder(SimulationConfiguration(duration=0.9))
        for cls, position in [(Satellite, (0, 0, 0)), (Peer, (50, 0, 0)),
                              (sensor(8), (-5, 0, 0)), (sensor(11), (-10, 0, 0)),
                              (Core, (25, 0, 0)), (Peer, (50, 20, 0))]:
            builder.add_node(cls, position)
        radio = Radio()
        builder.add_handler(TimerHandler())
        builder.add_handler(radio)
        simulation = builder.build()
        logging.getLogger().setLevel(logging.CRITICAL)
        simulation.start_simulation()
        nodes = [simulation.get_node(i).protocol_encapsulator.protocol for i in range(6)]
        return nodes, radio, snapshots

    def test_even_odd_batches_queued_offline_then_replicated_over_radio(self):
        nodes, radio, snapshots = self.run_network()
        pending, original = snapshots[0]
        self.assertEqual(original, {'sensor_8': 2, 'sensor_11': 2})
        self.assertEqual(len(pending), 2)
        self.assertEqual(snapshots[1][0], {})
        self.assertEqual(nodes[0].packets, original)
        self.assertEqual(len(radio.publishes), 2)  # further contacts do not republish
        for peer in (nodes[1], nodes[5]):
            even = peer.pspeer_service._topics.get_history('T2')
            odd = peer.pspeer_service._topics.get_history('T1')
            self.assertEqual(len(even), 1)
            self.assertEqual(len(odd), 1)
            self.assertEqual(even[0].payload, {'sensor_id': 8, 'packet_count': 2})
            self.assertEqual(odd[0].payload, {'sensor_id': 11, 'packet_count': 2})
            self.assertEqual({p.message_id for p in even + odd}, set(pending))
            self.assertTrue(all(p.origin_id == 0 and p.created_at == 0.2 for p in even + odd))

    def test_each_satellite_face_is_the_publication_origin_region(self):
        for face in ('N', 'S', 'E', 'W'):
            with self.subTest(face=face):
                nodes, _, _ = self.run_network(face=face)
                self.assertEqual(nodes[1].pspeer_service._topics.get_history('T2')[0].origin_region.value, face)

    def test_no_selected_peer_keeps_original_ids_until_later_contact(self):
        nodes, radio, snapshots = self.run_network(no_peer=True)
        self.assertEqual(snapshots[0][0], snapshots[1][0])
        self.assertEqual(len(radio.publishes), 2)
        self.assertEqual(nodes[0]._pending_sensor_publications, {})
        self.assertEqual({p['payload']['publication']['message_id'] for p in radio.publishes},
                         set(snapshots[0][0]))

    def test_submission_loss_is_not_claimed_as_delivery_or_retried(self):
        nodes, radio, _ = self.run_network(lose_publish=True)
        self.assertEqual(len(radio.publishes), 2)
        self.assertEqual(nodes[0]._pending_sensor_publications, {})
        self.assertEqual(nodes[1].pspeer_service._topics.get_history('T2'), ())

    def test_original_upload_and_departure_leave_pubsub_queue_independent(self):
        node = make_satellite('N', swcore=True, pubsub=True)()
        node.provider = Mock()
        node.provider.get_id.return_value = 77
        node.provider.current_time.return_value = 0.0
        node.initialize()
        node.handle_packet(json.dumps({'sender_type': 0, 'sender_id': 2, 'sensor_id': 8,
                                       'packets': {'sensor_8': 3}}))
        pending = dict(node._pending_sensor_publications)
        node._start_exchange(10)
        sent = [json.loads(c.args[0].message) for c in node.provider.send_communication_command.call_args_list]
        self.assertEqual(next(p for p in sent if p.get('msg_type') == 'dock_data')['payload'], {'sensor_8': 3})
        with patch('utils.metrics.stats.record_dock'):
            node._depart()
        self.assertEqual(node.packets, {})
        self.assertEqual(node._pending_sensor_publications, pending)

    def test_main_leaves_satellite_peer_discovery_to_contact(self):
        for enabled in (False, True):
            argv = ['main', '--no-viz', '--topology', 'star', '--routing-strategy', 'swcore']
            if enabled:
                argv.append('--pubsub')
            with (patch('sys.argv', argv), patch.object(main, 'PUBSUB_ENABLED', False),
                  patch.object(main, 'SimulationBuilder') as builder,
                  patch.object(main, 'make_satellite', wraps=main.make_satellite) as factory):
                builder.return_value.add_node.side_effect = range(100, 200)
                main.main()
            self.assertEqual([c.kwargs['pspeer_id'] for c in factory.call_args_list], [None] * 4)
