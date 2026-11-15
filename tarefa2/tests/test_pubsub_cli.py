"""CLI activation must preserve legacy mode and build the required topology."""
import unittest
from unittest.mock import patch

from src import main
from src.swcore_mixin import SWCoreMixin
from utils.common import config


class PubSubCliTests(unittest.TestCase):
    def test_legacy_defaults(self):
        with patch.object(main, 'PUBSUB_ENABLED', False):
            args = main.parse_args([])
        self.assertFalse(args.pubsub)
        self.assertEqual((args.topology, args.routing_strategy), ('random', 'flooding'))

    def test_pubsub_forces_required_options_for_all_valid_combinations(self):
        for topology in ('random', 'star'):
            for routing in ('flooding', 'dtn', 'geocasting', 'swcore'):
                with self.subTest(topology=topology, routing=routing):
                    args = main.parse_args(['--pubsub', '--topology', topology,
                                            '--routing-strategy', routing])
                    self.assertTrue(args.pubsub)
                    self.assertEqual((args.topology, args.routing_strategy), ('star', 'swcore'))

    def test_pubsub_alone_and_option_order(self):
        for argv in (['--pubsub'], ['--topology', 'random', '--routing-strategy',
                                  'flooding', '--pubsub']):
            with self.subTest(argv=argv):
                args = main.parse_args(argv)
                self.assertEqual((args.topology, args.routing_strategy), ('star', 'swcore'))

    def test_legacy_explicit_options_and_other_flags_are_preserved(self):
        with patch.object(main, 'PUBSUB_ENABLED', False):
            args = main.parse_args(['--topology', 'star', '--routing-strategy', 'dtn',
                                    '--no-viz', '--force-regen'])
        self.assertFalse(args.pubsub)
        self.assertEqual((args.topology, args.routing_strategy), ('star', 'dtn'))
        self.assertTrue(args.no_viz)
        self.assertTrue(args.force_regen)

    def test_configuration_can_enable_mode_by_default(self):
        with patch.object(main, 'PUBSUB_ENABLED', True):
            args = main.parse_args([])
        self.assertTrue(args.pubsub)
        self.assertEqual((args.topology, args.routing_strategy), ('star', 'swcore'))

    def test_cli_does_not_mutate_configuration_or_leak_into_next_parse(self):
        with patch.object(main, 'PUBSUB_ENABLED', False):
            original = config.PUBSUB_ENABLED
            main.parse_args(['--pubsub'])
            self.assertEqual(config.PUBSUB_ENABLED, original)
            self.assertFalse(main.parse_args([]).pubsub)

    def test_configured_peer_slots_and_event_parameters(self):
        self.assertEqual(config.PUBSUB_TOPICS, ('T1', 'T2'))
        self.assertEqual(len(set(config.PSPEER_SLOTS)), 3)
        self.assertTrue(all(0 <= slot < config.CORE_RIM_NODES
                            for slot in config.PSPEER_SLOTS))
        self.assertIsInstance(config.PUBSUB_SEED, int)
        self.assertGreater(config.PUBSUB_PUBLICATION_INTERVAL, 0)
        self.assertGreater(config.PUBSUB_SUBSCRIPTION_INTERVAL, 0)

    def test_main_builds_star_swcore_and_enables_satellite_handshake(self):
        with (patch('sys.argv', ['src.main', '--pubsub', '--no-viz']),
              patch.object(main, 'SimulationBuilder') as builder,
              patch.object(main, 'make_satellite', wraps=main.make_satellite) as satellite,
              patch.object(main, 'make_random_uav') as random_uav,
              patch.object(main.random, 'seed')):
            main.main()
        calls = builder.return_value.add_node.call_args_list
        sensor_count = len(config.SENSOR_POSITIONS)
        cores = calls[sensor_count:sensor_count + 1 + config.CORE_RIM_NODES]
        self.assertEqual(len(calls), sensor_count + 1 + config.CORE_RIM_NODES + 4)
        self.assertTrue(all(issubclass(call.args[0], SWCoreMixin) for call in cores))
        self.assertEqual(satellite.call_count, 4)
        self.assertTrue(all(call.kwargs['swcore'] for call in satellite.call_args_list))
        random_uav.assert_not_called()
        builder.return_value.build.return_value.start_simulation.assert_called_once()


if __name__ == '__main__':
    unittest.main()
