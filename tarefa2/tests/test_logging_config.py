import io
import logging
from pathlib import Path
import unittest
from unittest.mock import patch
from tempfile import TemporaryDirectory

from gradysim.simulator.log import setup_simulation_formatter

from utils.common.logging_config import configure_logging


class LoggingConfigTests(unittest.TestCase):
    def setUp(self):
        self.root = logging.getLogger()
        self.old_level = self.root.level
        self.old_handlers = self.root.handlers[:]
        self.root.handlers = []
        self.output = io.StringIO()
        self.handler = logging.StreamHandler(self.output)
        self.handler.setFormatter(logging.Formatter('%(levelname)s:%(message)s'))
        self.root.addHandler(self.handler)
        self.addCleanup(self.restore)

    def restore(self):
        self.root.handlers = self.old_handlers
        self.root.setLevel(self.old_level)
        self.handler.close()

    def library_record(self, level=logging.INFO):
        return logging.LogRecord('root', level,
                                 str(Path('site-packages/gradysim/simulator/simulation.py')),
                                 1, 'library message', (), None)

    def test_info_hides_existing_debug_and_library_status_but_allows_new_info(self):
        configure_logging('INFO')
        logging.debug('existing trace')
        self.root.handle(self.library_record())
        logging.info('new application info')
        self.assertEqual(self.output.getvalue(), 'INFO:new application info\n')

    def test_debug_shows_library_status_as_debug(self):
        configure_logging('DEBUG')
        self.root.handle(self.library_record())
        self.assertEqual(self.output.getvalue(), 'DEBUG:library message\n')

    def test_library_runtime_errors_remain_visible(self):
        configure_logging('INFO')
        self.root.handle(self.library_record(logging.ERROR))
        self.assertEqual(self.output.getvalue(), 'ERROR:library message\n')

    def test_execution_start_end_and_elapsed_time_remain_info(self):
        configure_logging('INFO')
        messages = (
            '[--------- Simulation started ---------]',
            '[--------- Simulation finished ---------]',
            'Real time elapsed: 0:00:01',
        )
        for message in messages:
            record = self.library_record()
            record.msg = message
            self.root.handle(record)
        self.assertEqual(self.output.getvalue(),
                         ''.join(f'INFO:{message}\n' for message in messages))

    def test_reconfiguration_covers_new_simulator_handler_without_duplicate_filters(self):
        configure_logging('INFO')
        configure_logging('INFO')
        other = logging.StreamHandler(self.output)
        self.root.addHandler(other)
        configure_logging('INFO')
        self.assertEqual(len(self.handler.filters), 1)
        self.assertEqual(len(other.filters), 1)
        self.root.handle(self.library_record())
        self.assertEqual(self.output.getvalue(), '')

    def test_simulator_console_replaces_default_console_and_keeps_file_output(self):
        with TemporaryDirectory() as directory:
            file_handler = logging.FileHandler(Path(directory) / 'simulation.log')
            self.root.addHandler(file_handler)
            try:
                with patch('sys.stderr', self.output):
                    setup_simulation_formatter(False, None)
                configure_logging('INFO')
                logging.info('Simulation complete.')
                self.assertEqual(self.output.getvalue(), 'INFO     Simulation complete.\n')
                self.assertIn(file_handler, self.root.handlers)
                file_handler.flush()
                self.assertEqual((Path(directory) / 'simulation.log').read_text(),
                                 'Simulation complete.\n')
            finally:
                self.root.removeHandler(file_handler)
                file_handler.close()

    def test_repeated_simulator_setup_keeps_only_latest_console_formatter(self):
        with patch('sys.stderr', self.output):
            setup_simulation_formatter(False, None)
            configure_logging('INFO')
            newest = setup_simulation_formatter(False, None)
        configure_logging('INFO')
        configure_logging('INFO')
        console = [handler for handler in self.root.handlers
                   if type(handler) is logging.StreamHandler]
        self.assertEqual(len(console), 1)
        self.assertIs(console[0].formatter, newest)
        logging.info('Simulation complete.')
        self.assertEqual(self.output.getvalue(), 'INFO     Simulation complete.\n')


if __name__ == '__main__':
    unittest.main()
