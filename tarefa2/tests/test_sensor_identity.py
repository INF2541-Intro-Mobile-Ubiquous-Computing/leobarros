"""Stable sensor identity/parity while retaining the original radio collection."""
import json
import logging
import unittest
from unittest.mock import Mock, patch

from gradysim.protocol.messages.communication import BroadcastMessageCommand
from gradysim.simulator.handler.communication import CommunicationHandler, CommunicationMedium
from gradysim.simulator.handler.timer import TimerHandler
from gradysim.simulator.simulation import SimulationBuilder, SimulationConfiguration

from src import main
from src.sensor import make_sensor
from src.satellite import make_satellite_protocol, ST_COLLECT_OUT
from utils.actor_templates.sensor_template import SensorProtocol
from utils.common.config import SENSOR_POSITIONS
from utils.common.sensor_identity import sensor_id_from_name, topic_for_sensor
import test_pubsub_transport as transport_tests


class SensorIdentityTests(unittest.TestCase):
    setUp = transport_tests.PubSubTransportTests.setUp

    def test_configured_ids_are_unique_canonical_and_cover_both_parities(self):
        ids = [sensor_id_from_name(name) for name in SENSOR_POSITIONS]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual({i % 2 for i in ids}, {0, 1})
        self.assertEqual({topic_for_sensor(i) for i in ids}, {'T1', 'T2'})
        for name in SENSOR_POSITIONS:
            self.assertEqual(f'sensor_{make_sensor(name).sensor_id}', name)

    def test_identity_and_parity_do_not_depend_on_simulator_node_id(self):
        for logical_id, topic in ((0, 'T2'), (8, 'T2'), (11, 'T1')):
            for node_id in (0, 47):
                # Run the underlying template to avoid visualization in this unit test.
                class NamedSensor(SensorProtocol):
                    sensor_id = make_sensor(f'sensor_{logical_id}').sensor_id
                sensor = NamedSensor()
                sensor.provider = Mock()
                sensor.provider.get_id.return_value = node_id
                sensor.provider.current_time.return_value = 0.0
                with self.assertLogs(level='DEBUG') as logs:
                    sensor.initialize()
                self.assertIn(f'sensor_id={logical_id}', logs.output[0])
                self.assertIn(f'topic={topic}', logs.output[0])
                sensor.handle_timer('gen')
                sensor.handle_packet(json.dumps({'sender_type': 1, 'sender_id': 99}))
                raw = json.loads(sensor.provider.send_communication_command.call_args.args[0].message)
                self.assertEqual(raw['packets'], {f'sensor_{logical_id}': 1})
                self.assertEqual((raw['sender_id'], raw['sensor_id']), (node_id, logical_id))
                self.assertEqual(sensor.packet_count, 0)

    def test_invalid_identity_rejected_instead_of_aliasing_another_sensor(self):
        for name in ('sensor_-1', 'sensor_01', 'sensor_+1', 'sensor_1.0', 'other_1', None):
            with self.assertRaises(ValueError):
                make_sensor(name)
        for value in (-1, True, '2', 1.5):
            with self.assertRaises(ValueError):
                topic_for_sensor(value)

    def test_main_binds_names_from_layout_even_when_order_is_reversed(self):
        layout = {'sensor_11': (1, 2, 0), 'sensor_8': (3, 4, 0)}
        with (patch.object(main, 'SENSOR_POSITIONS', layout),
              patch('sys.argv', ['main', '--pubsub', '--no-viz']),
              patch.object(main, 'SimulationBuilder') as builder):
            main.main()
        calls = builder.return_value.add_node.call_args_list[:2]
        self.assertEqual([call.args[0].sensor_id for call in calls], [11, 8])
        self.assertEqual([call.args[1] for call in calls], list(layout.values()))

    def test_radio_collection_keeps_counts_and_names_for_even_and_odd_sensors(self):
        class Collector(make_satellite_protocol('N', swcore=True)):
            def initialize(self):
                self._state = ST_COLLECT_OUT
                self.packets = {}
                self.provider.schedule_timer('collect', 0.02)
                self.provider.schedule_timer('collect', 0.03)

            def handle_timer(self, timer):
                self.provider.send_communication_command(BroadcastMessageCommand(json.dumps({
                    'sender_type': 1, 'sender_id': self.provider.get_id()})))

            def finish(self):
                pass

        def seeded_sensor(name):
            class Seeded(make_sensor(name)):
                def initialize(self):
                    super().initialize()
                    self.handle_timer('gen')
                    self.handle_timer('gen')

                def finish(self):
                    pass  # avoid mutating global legacy metrics in this test
            return Seeded

        builder = SimulationBuilder(SimulationConfiguration(duration=0.04))
        builder.add_node(Collector, (0, 0, 0))  # node ordering intentionally differs from main
        builder.add_node(seeded_sensor('sensor_8'), (5, 0, 0))
        builder.add_node(seeded_sensor('sensor_11'), (10, 0, 0))
        builder.add_handler(TimerHandler())
        builder.add_handler(CommunicationHandler(CommunicationMedium(transmission_range=30)))
        simulation = builder.build()
        logging.getLogger().setLevel(logging.CRITICAL)
        simulation.start_simulation()
        nodes = [simulation.get_node(i).protocol_encapsulator.protocol for i in range(3)]
        self.assertEqual(nodes[0].packets, {'sensor_8': 2, 'sensor_11': 2})
        self.assertEqual([n.sensor_topic for n in nodes[1:]], ['T2', 'T1'])
        self.assertEqual([n.packet_count for n in nodes[1:]], [0, 0])
        self.assertEqual([n.total_produced for n in nodes[1:]], [2, 2])
        self.assertEqual([n.total_expired for n in nodes[1:]], [0, 0])
