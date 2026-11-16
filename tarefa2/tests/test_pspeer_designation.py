import io
import unittest
from unittest.mock import Mock, patch

from src import main
from src.pubsub.models import Publication, Region, Subscription
from src.pubsub.pspeer_mixin import PSPeerMixin
from src.swcore_mixin import SWCoreMixin
from src.uav import RimVizMixin, make_core_rim
from utils.common.config import PSPEER_COLOR, PSPEER_SLOTS
from utils.viz_templates.constants import COLOR_CORE_RIM


class PSPeerDesignationTests(unittest.TestCase):
    def test_main_designates_configured_slots_only_in_pubsub_mode(self):
        for enabled in (False, True):
            with self.subTest(enabled=enabled):
                argv = ['main', '--no-viz', '--topology', 'star', '--routing-strategy', 'swcore']
                if enabled:
                    argv.append('--pubsub')
                with (patch('sys.argv', argv), patch.object(main, 'PUBSUB_ENABLED', False),
                      patch.object(main, 'SimulationBuilder') as builder,
                      patch.object(main.random, 'seed')):
                    main.main()
                calls = builder.return_value.add_node.call_args_list
                core = calls[len(main.SENSOR_POSITIONS):len(main.SENSOR_POSITIONS) + 9]
                peers = [call.args[0] for call in core if issubclass(call.args[0], PSPeerMixin)]
                self.assertEqual([cls.pspeer_slot for cls in peers], list(PSPEER_SLOTS) if enabled else [])
                self.assertEqual(len(calls), len(main.SENSOR_POSITIONS) + 13)
                self.assertTrue(all(issubclass(call.args[0], SWCoreMixin) for call in core))
                self.assertEqual([call.args[1] for call in core],
                                 [main.CORE_HUB_START, *main.CORE_RIM_STARTS])

    def test_service_initialization_is_cooperative_and_instance_local(self):
        class Base:
            def initialize(self):
                self.base_initialized = True

        class Peer(PSPeerMixin, Base):
            pspeer_slot = 3

        peers = [Peer(), Peer()]
        with self.assertLogs(level='INFO') as logs:
            for index, peer in enumerate(peers):
                peer.provider = Mock()
                peer.provider.get_id.return_value = 40 + index
                peer.initialize()
                self.assertTrue(peer.base_initialized)
        self.assertIn('PSPEER 40 (slot 3) was initialized.', logs.output[0])
        self.assertIsNot(peers[0].pspeer_service, peers[1].pspeer_service)
        for peer in peers:
            peer.pspeer_service.subscribe(Subscription(10, 'T1', {Region.N}))
        peers[0].pspeer_service.publish(Publication('one', 'T1', 12, Region.N, 0, {}))
        self.assertEqual(peers[1].pspeer_service.fetch(10, 'T1'), ())

    def test_visual_color_and_mobility_callbacks_are_preserved(self):
        for peer in (False, True):
            plain = make_core_rim(3, 'swcore', viz=False, pspeer=peer)
            visual = make_core_rim(3, 'swcore', viz=True, pspeer=peer)
            self.assertEqual(plain.handle_telemetry.__qualname__, visual.handle_telemetry.__qualname__)
            node = visual()
            node.provider = Mock()
            node.provider.get_id.return_value = 99
            node._vc = Mock()
            node._paint_rim()
            node._vc.paint_node.assert_called_once_with(99, PSPEER_COLOR if peer else COLOR_CORE_RIM)
            self.assertIn(RimVizMixin, visual.__mro__)
            self.assertEqual(issubclass(plain, PSPeerMixin), peer)

    def test_invalid_peer_slot_configuration_is_rejected_only_when_enabled(self):
        for slots in ((0, 0, 6), (0, 3), (0, 3, 8), (-1, 3, 6), (0, '3', 6)):
            with self.subTest(slots=slots), patch.object(main, 'PSPEER_SLOTS', slots):
                with patch('sys.stderr', io.StringIO()), self.assertRaises(SystemExit) as error:
                    main.parse_args(['--pubsub'])
                self.assertEqual(error.exception.code, 2)
                with patch.object(main, 'PUBSUB_ENABLED', False):
                    self.assertFalse(main.parse_args([]).pubsub)
