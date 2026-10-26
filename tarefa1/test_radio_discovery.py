import json
import unittest
from unittest.mock import Mock, patch

from gradysim.protocol.messages.communication import CommunicationCommandType
from communicable_uav_protocol import CommunicableUAVProtocol
from message_transmitter_uav_protocol import MessageTransmitterUAVProtocol
from movable_core_uav_protocol import MovableCoreUAVProtocol
from flight_plan import FlightPlan
import constants


class RadioDiscoveryTest(unittest.TestCase):
    def setUp(self):
        self.external = CommunicableUAVProtocol.with_external(0)()
        self.external.provider = Mock()
        self.external.provider.get_id.return_value = constants.DRONE_COUNT
        self.external.provider.current_time.return_value = 0
        with patch('visible_node_protocol.VisualizationController'):
            self.external.initialize()
        self.external.current_position = self.external.contact_point
        self.external.mode = 'waiting'
        self.external.wait_for_core(0)
        self.request = json.loads(self.external.provider.send_communication_command.call_args.args[0].message)

    def offer(self, core=7, **fields):
        packet = dict(type='station_offer', request_id=self.external.query_id, external_index=0, core_id=core)
        packet.update(fields)
        return json.dumps(packet)

    def test_first_offer_wins_and_data_is_unicast_only_after_arrival(self):
        self.assertEqual(self.external.message_sequence, 0)
        self.external.handle_packet(self.offer(7))
        self.external.handle_packet(self.offer(0))
        self.assertEqual(self.external.target_index, 7)
        self.assertEqual(self.external.message_sequence, 1)
        self.assertEqual(self.external.mode, 'contact')
        commands = [c.args[0] for c in self.external.provider.send_communication_command.call_args_list]
        data = [c for c in commands if json.loads(c.message)['type'] == 'data']
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0].destination, 7)
        self.assertEqual(data[0].command_type, CommunicationCommandType.SEND)
        self.assertEqual(self.external.destination, self.external.contact_point)

    def test_stale_wrong_and_en_route_offers_are_ignored(self):
        for packet in (self.offer(request_id='old'), self.offer(external_index=1), self.offer(core=True)):
            self.external.handle_packet(packet)
        self.external.mode = 'seek'
        self.external.handle_packet(self.offer())
        self.external.mode = 'waiting'
        self.external.provider.current_time.return_value = self.external.query_deadline
        self.external.handle_packet(self.offer())
        self.assertEqual(self.external.message_sequence, 0)

    def test_no_offer_means_waiting_and_retry_without_leaving_station(self):
        for now in (1, 2, 10):
            self.external.provider.current_time.return_value = now
            self.external.handle_timer(constants.MOVEMENT_TIMER)
        self.assertEqual(self.external.mode, 'waiting')
        self.assertEqual(self.external.message_sequence, 0)
        self.assertEqual(self.external.current_position, self.external.contact_point)
        self.assertGreater(self.external.discovery_sequence, 1)

    def test_only_core_within_contact_distance_replies_directly(self):
        core = MessageTransmitterUAVProtocol()
        core.provider = Mock()
        core.provider.get_id.return_value = 7
        core.provider.current_time.return_value = 0
        with patch.object(MovableCoreUAVProtocol, 'initialize'):
            core.initialize()
        core.flight_plan = FlightPlan(constants.EXTERNAL_CORE_TARGETS, constants.DRONE_COUNT)
        core.current_position = (20, 0, 0)  # Dentro do rádio de 30 m, fora do contato de 5 m.
        core.handle_packet(json.dumps(self.request))
        core.provider.send_communication_command.assert_not_called()
        core.current_position = (30, 0, 0)
        core.handle_packet(json.dumps(self.request))
        command = core.provider.send_communication_command.call_args.args[0]
        self.assertEqual(command.command_type, CommunicationCommandType.SEND)
        self.assertEqual(command.destination, constants.DRONE_COUNT)
        self.external.handle_packet(command.message)
        self.assertEqual(self.external.target_index, 7)


if __name__ == '__main__':
    unittest.main()
