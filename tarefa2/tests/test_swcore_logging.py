"""Check SwCore visibility and the simulator's logging-level override."""
import io
import logging
import unittest
from unittest.mock import Mock, patch

from src import main
from src.swcore_mixin import SWCoreMixin


class SwCoreLoggingTests(unittest.TestCase):
    def setUp(self):
        self.root = logging.getLogger()
        previous_level = self.root.level
        self.addCleanup(self.root.setLevel, previous_level)
        self.output = io.StringIO()
        self.handler = logging.StreamHandler(self.output)
        self.handler.setFormatter(logging.Formatter('%(levelname)s:%(message)s'))
        self.root.addHandler(self.handler)
        self.addCleanup(self.root.removeHandler, self.handler)

    def exercise_swcore_events(self):
        core = SWCoreMixin()
        core.provider = Mock()
        core.provider.get_id.return_value = 10
        core.provider.current_time.return_value = 1.0
        core._rt = {}
        core._ver_counter = 0
        core._core_buffer = {}
        core._send_rt_update = Mock()
        core._on_connect(20, 'N')
        core._on_disconnect(20)
        core._on_rt_update(dict(sat=21, sender_id=11, state='reachable', ver=[2, 11, 1]))

    def test_all_swcore_events_are_visible_at_debug(self):
        self.root.setLevel(logging.DEBUG)
        self.exercise_swcore_events()
        lines = self.output.getvalue().splitlines()
        self.assertEqual(len(lines), 3)
        self.assertTrue(all(line.startswith('DEBUG:[SWCORE') for line in lines))
        self.assertIn('connect(20)', lines[0])
        self.assertIn('disconnect(20)', lines[1])
        self.assertIn('RT[21]=reachable', lines[2])

    def test_swcore_events_are_hidden_at_info_and_above(self):
        for level in ('INFO', 'WARNING', 'ERROR', 'CRITICAL'):
            with self.subTest(level=level):
                self.root.setLevel(level)
                self.exercise_swcore_events()
                self.assertEqual(self.output.getvalue(), '')

    def test_main_reapplies_configured_level_after_simulator_build(self):
        for level in ('DEBUG', 'INFO', 'WARNING'):
            with self.subTest(level=level):
                simulation = Mock()

                def build():
                    # Reproduce GrADyS-SIM's reset of the global threshold.
                    self.root.setLevel(logging.INFO)
                    return simulation

                def start():
                    self.assertEqual(self.root.level, getattr(logging, level))

                simulation.start_simulation.side_effect = start
                with (patch.object(main, 'LOG_LEVEL', level),
                      patch.object(main, 'SimulationBuilder') as builder,
                      patch.object(main.random, 'seed'),
                      patch('sys.argv', ['src.main', '--pubsub', '--no-viz'])):
                    builder.return_value.build.side_effect = build
                    main.main()
                simulation.start_simulation.assert_called_once()


if __name__ == '__main__':
    unittest.main()
