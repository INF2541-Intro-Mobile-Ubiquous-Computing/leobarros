import json
import random
import unittest
from unittest.mock import Mock, patch

from gradysim.protocol.messages.communication import CommunicationCommandType

import constants
from communicable_uav_protocol import CommunicableUAVProtocol
from flight_plan import FlightPlan
from message_transmitter_uav_protocol import MessageTransmitterUAVProtocol
from movable_core_uav_protocol import MovableCoreUAVProtocol
from random_core_motion import RandomCoreMotion
from simulation_metrics import SimulationMetrics


class RadioDiscoveryTest(unittest.TestCase):
    def setUp(self):
        mode = patch.object(constants, 'SIMULATION_MODE', constants.RANDOM)
        mode.start()
        self.addCleanup(mode.stop)
        self.external = CommunicableUAVProtocol.with_external(0)()
        self.external.provider = Mock()
        self.external.provider.get_id.return_value = constants.DRONE_COUNT
        self.external.provider.current_time.return_value = 0
        with patch('visible_node_protocol.VisualizationController'):
            self.external.initialize()
        self.external.metrics = SimulationMetrics()
        self.external.current_position = self.external.target_position(0)
        self.external.steer = Mock()
        self.external.mode = 'seek'
        self.external.start_away(0)
        self.request = self.external.discovery_request

    def response(self, **overrides):
        packet = dict(self.request, type='position_plan', plan=dict(
            reference_time=0, relative_position=[constants.FORMATION_RADIUS - 2, 0], velocity=[0, 0], valid_until=0.8))
        packet.update(overrides)
        return packet

    def core(self, index):
        core = MessageTransmitterUAVProtocol()
        core.provider = Mock()
        core.provider.get_id.return_value = index
        core.provider.current_time.return_value = 0
        with patch.object(MovableCoreUAVProtocol, 'initialize'):
            core.initialize()
        core.flight_plan = FlightPlan(constants.EXTERNAL_CORE_TARGETS, constants.DRONE_COUNT)
        core.random_motion = RandomCoreMotion(10, 6, 1, index * 40, random.Random(19))
        return core

    def test_no_data_before_direct_contact_confirmation(self):
        self.assertEqual(self.external.mode, 'query')
        self.assertEqual(self.external.message_sequence, 0)
        self.assertFalse(hasattr(self.external, 'position_lookup'))
        response = self.response()
        self.external.handle_packet(json.dumps(response))
        self.assertEqual(self.external.mode, 'intercept')
        self.external.provider.current_time.return_value = 0.1
        self.external.handle_timer(constants.MOVEMENT_TIMER)
        self.assertEqual(self.external.mode, 'probe')
        command = self.external.provider.send_communication_command.call_args.args[0]
        self.assertEqual(command.command_type, CommunicationCommandType.SEND)
        self.assertEqual(json.loads(command.message)['type'], 'contact_probe')
        self.assertEqual(self.external.message_sequence, 0)
        self.external.handle_packet(json.dumps(dict(response, type='contact_ready')))
        self.assertEqual(self.external.mode, 'contact')
        self.assertEqual(self.external.message_sequence, 1)
        self.assertEqual(self.external.metrics.summary()['total']['discovery']['contact_confirmed'], 1)

    def test_request_and_response_flood_only_once_per_relay(self):
        relay = self.core(1)
        for packet in (self.request, self.request, self.response(), self.response()):
            relay.handle_packet(json.dumps(packet))
        commands = relay.provider.send_communication_command.call_args_list
        self.assertEqual(len(commands), 2)
        self.assertTrue(all(call.args[0].command_type == CommunicationCommandType.BROADCAST for call in commands))
        relay.handle_packet(json.dumps(dict(self.response(), type='contact_ready')))
        self.assertEqual(relay.provider.send_communication_command.call_count, 2)

    def test_target_announces_snapshot_and_rejects_probe_after_expiry(self):
        core = self.core(0)
        core.handle_packet(json.dumps(self.request))
        response = json.loads(core.provider.send_communication_command.call_args.args[0].message)
        self.assertEqual(response['type'], 'position_plan')
        self.assertLessEqual(response['plan']['valid_until'], 1)
        probe = dict(self.request, type='contact_probe')
        core.handle_packet(json.dumps(probe))
        command = core.provider.send_communication_command.call_args.args[0]
        self.assertEqual(command.command_type, CommunicationCommandType.SEND)
        self.assertEqual(command.destination, constants.DRONE_COUNT)
        self.assertEqual(json.loads(command.message)['type'], 'contact_ready')
        core.provider.send_communication_command.reset_mock()
        core.provider.current_time.return_value = response['plan']['valid_until']
        core.handle_packet(json.dumps(probe))
        core.provider.send_communication_command.assert_not_called()

    def test_timeout_waits_for_next_visit_and_ignores_old_response(self):
        self.external.provider.current_time.return_value = constants.DISCOVERY_RESPONSE_TIMEOUT
        self.external.handle_timer(constants.DISCOVERY_TIMER)
        self.assertEqual(self.external.mode, 'away')
        self.assertEqual(self.external.message_sequence, 0)
        self.assertEqual(self.external.metrics.discovery['no_response'], 1)
        self.external.handle_packet(json.dumps(self.response()))
        self.assertEqual(self.external.mode, 'away')
        self.external.begin_discovery(2)
        self.external.handle_packet(json.dumps(self.response()))
        self.assertEqual(self.external.mode, 'query')

    def test_expired_plan_and_unreachable_plan_fail_without_data(self):
        self.external.provider.current_time.return_value = 0.9
        self.external.handle_packet(json.dumps(self.response()))
        self.assertEqual(self.external.mode, 'away')
        self.assertEqual(self.external.metrics.discovery['expired_response'], 1)
        self.external.provider.current_time.return_value = 2
        self.external.current_position = (34, 0, 0)
        self.external.begin_discovery(2)
        response = dict(self.external.discovery_request, type='position_plan', plan=dict(
            reference_time=2, relative_position=[-10, 0], velocity=[0, 0], valid_until=2.01))
        self.external.handle_packet(json.dumps(response))
        self.assertEqual(self.external.mode, 'away')
        self.assertEqual(self.external.metrics.discovery['intercept_failed'], 1)
        self.assertEqual(self.external.message_sequence, 0)

    def test_lost_probe_reply_fails_and_expired_ready_cannot_send_data(self):
        response = self.response()
        self.external.handle_packet(json.dumps(response))
        self.external.provider.current_time.return_value = 0.1
        self.external.handle_timer(constants.MOVEMENT_TIMER)
        self.external.provider.current_time.return_value = self.external.discovery_deadline
        self.external.handle_timer(constants.DISCOVERY_TIMER)
        self.external.handle_packet(json.dumps(dict(response, type='contact_ready')))
        self.assertEqual(self.external.mode, 'away')
        self.assertEqual(self.external.metrics.discovery['intercept_failed'], 1)
        self.assertEqual(self.external.message_sequence, 0)

    def test_mini_plan_does_not_predict_new_random_direction(self):
        rng = random.Random(19)
        motion = RandomCoreMotion(1, 4, 10, 0, rng)
        before = rng.getstate()
        plan = motion.mini_plan()
        self.assertEqual(rng.getstate(), before)
        self.assertEqual(motion.time, 0)
        self.assertLessEqual(plan['valid_until'], 0.5)
        expected = tuple(p + v * plan['valid_until']
                         for p, v in zip(plan['relative_position'], plan['velocity']))
        actual = motion.position_at(plan['valid_until'])
        for coordinate, result in zip(expected, actual):
            self.assertAlmostEqual(coordinate, result)


if __name__ == '__main__':
    unittest.main()
