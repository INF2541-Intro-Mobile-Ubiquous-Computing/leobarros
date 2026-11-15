"""Characterize the inherited behavior documented in docs/architecture.md.

These tests describe the baseline, including limitations; they are not Pub/Sub
requirements. No radio delivery is inferred from a recorded send command.
"""
import json
import unittest
from unittest.mock import Mock, patch

from src import dock_mixin
from src.dock_mixin import CoreDockMixin
from src.neighbor_mixin import NeighborMixin
from src.satellite import make_satellite_protocol
from src.swcore_mixin import DIRECT, HOP, SWCoreMixin
from src.uav import make_core_hub, make_core_rim, make_random_uav
from utils.actor_templates.sensor_template import SensorProtocol
from utils.common.config import EXCHANGE_TIMEOUT, SWCORE_MAX_HOPS
from utils.metrics import stats


class CoreHarness(CoreDockMixin, SWCoreMixin):
    """Use real routing/delivery methods without mobility plugins."""

    def __init__(self):
        self.provider = Mock()
        self.provider.get_id.return_value = 10
        self.provider.current_time.return_value = 5.0
        self._core_buffer = {}
        self._rt = {}
        self._ver_counter = 0
        self.fresh_neighbors = Mock(return_value={11: {'role': 'rim0'}})


def message():
    return dict(id='sample', origin_face='N', dest_face='S',
                origin_sat=20, dest_sat=21, payload={'sensor_0': 1},
                created_at=0.0, hops=1)


class ArchitectureContractsTests(unittest.TestCase):
    def setUp(self):
        # Restore inherited registries after every test, including on failure.
        for registry in (dock_mixin._SAT_BY_FACE, dock_mixin._DOCKED_SATS,
                         stats._MESSAGES, stats._SATELLITES, stats.SENSOR_STATS):
            self.enterContext(patch.dict(registry, {}, clear=True))
        self.core = CoreHarness()

    def sent(self):
        return [(call.args[0].destination, json.loads(call.args[0].message))
                for call in self.core.provider.send_communication_command.call_args_list]

    def buffer(self):
        entry = message()
        self.core._core_buffer[entry['id']] = entry
        return entry

    def test_factory_mro_exposes_upload_hook_and_shadows_route_in_core(self):
        for cls in (make_core_hub('swcore'), make_core_rim(0, 'swcore'),
                    make_random_uav('swcore')):
            with self.subTest(protocol=cls.__name__):
                self.assertEqual(cls.__mro__[1:4],
                                 (NeighborMixin, CoreDockMixin, SWCoreMixin))
                self.assertIs(cls.route_in_core, CoreDockMixin.route_in_core)
                self.assertIs(cls.on_dock_upload, SWCoreMixin.on_dock_upload)

    def test_unknown_satellite_route_keeps_message_without_transmission(self):
        entry = self.buffer()
        self.core._route(entry)
        self.assertIn(entry['id'], self.core._core_buffer)
        self.assertEqual(self.sent(), [])

    def test_hop_forwarding_removes_custody_before_any_ack(self):
        entry = self.buffer()
        self.core._rt[21] = dict(state=HOP, next_hop=11, ver=[1, 11, 1])
        self.core._route(entry)
        target, raw = self.sent()[0]
        self.assertEqual((target, raw['next_hop'], raw['msg_type']),
                         (11, 11, 'routing_swcore'))
        self.assertEqual(raw['hops'], 2)
        self.assertNotIn(entry['id'], self.core._core_buffer)

    def test_hop_limit_keeps_message_in_buffer(self):
        entry = self.buffer()
        entry['hops'] = SWCORE_MAX_HOPS
        self.assertFalse(self.core._forward(entry, 11))
        self.assertIn(entry['id'], self.core._core_buffer)
        self.assertEqual(self.sent(), [])

    def test_direct_delivery_does_not_apply_forwarding_hop_limit(self):
        entry = self.buffer()
        entry['hops'] = SWCORE_MAX_HOPS
        self.core._rt[21] = dict(state=DIRECT, next_hop=None, ver=[1, 10, 1])
        self.core._route(entry)
        target, raw = self.sent()[0]
        self.assertEqual((target, raw['msg_type']), (21, 'dock_deliver'))
        self.assertEqual(raw['hops'], SWCORE_MAX_HOPS + 1)
        self.assertNotIn(entry['id'], self.core._core_buffer)

    def test_stale_route_update_cannot_replace_newer_state(self):
        row = dict(state=DIRECT, next_hop=None, ver=[5, 10, 2])
        self.core._rt[21] = row.copy()
        for version in ([4, 11, 99], [5, 10, 2]):
            self.core._on_rt_update(dict(sat=21, sender_id=11,
                                         state='unreachable', ver=version))
            self.assertEqual(self.core._rt[21], row)
        self.assertEqual(self.sent(), [])

    def test_reverse_channel_delivers_even_without_direct_route(self):
        entry = self.buffer()
        self.assertFalse(self.core.deliver_on_alignment)
        self.core._try_deliver('S', 21)
        self.assertEqual(self.core._rt, {})
        self.assertEqual(self.sent()[0][1]['msg_type'], 'dock_deliver')
        self.assertNotIn(entry['id'], self.core._core_buffer)

    def test_first_sensor_payload_name_is_offset_from_node_id(self):
        sensor = SensorProtocol()
        sensor.provider = Mock()
        sensor.provider.get_id.return_value = 0
        sensor.provider.current_time.return_value = 0.0
        sensor.initialize()
        sensor.handle_timer('gen')
        sensor.handle_packet(json.dumps(dict(sender_type=1, sender_id=20)))
        command = sensor.provider.send_communication_command.call_args.args[0]
        raw = json.loads(command.message)
        self.assertEqual(raw['sender_id'], 0)
        self.assertEqual(raw['packets'], {'sensor_-1': 1})

    def test_satellite_connects_on_first_ack_and_disconnects_on_timeout(self):
        satellite = make_satellite_protocol('N', swcore=True)()
        satellite.provider = Mock()
        satellite.provider.get_id.return_value = 20
        satellite.provider.current_time.return_value = 0.0
        satellite.initialize()
        self.assertEqual(satellite._state, 'COLLECT_OUT')
        satellite._start_wait_align()
        for node in (10, 11):
            satellite.handle_packet(json.dumps(dict(msg_type='dock_ack',
                                                    face='N', sender_id=node)))
        self.assertEqual(satellite._ack_node, 10)
        self.assertEqual(satellite._state, 'EXCHANGE')
        satellite.provider.schedule_timer.assert_any_call(
            'sat_exchange_timeout', EXCHANGE_TIMEOUT)
        satellite.handle_timer('sat_exchange_timeout')
        self.assertEqual(satellite._state, 'COLLECT_OUT')
        commands = satellite.provider.send_communication_command.call_args_list
        events = [(c.args[0].destination, json.loads(c.args[0].message)['msg_type'])
                  for c in commands]
        self.assertEqual(events, [(10, 'dock_connect'), (10, 'dock_disconnect')])


if __name__ == '__main__':
    unittest.main()
