import io
import logging
import random
import unittest
from unittest.mock import patch

from gradysim.simulator.simulation import SimulationBuilder

import constants
import main
from real_time_handler import RealTimeHandler


class SimulationLoggingTest(unittest.TestCase):
    def test_main_respects_log_level_hierarchy(self):
        original_add_handler = SimulationBuilder.add_handler

        def add_handler(builder, handler):
            # Executa o main real, sem navegador nem espera de tempo real.
            if not isinstance(handler, RealTimeHandler):
                original_add_handler(builder, handler)

        root = logging.getLogger()
        old_level = root.level
        try:
            for level in ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'):
                with self.subTest(level=level):
                    output = io.StringIO()
                    rng = random.Random(19)
                    with patch.object(constants, 'LOG_LEVEL', level), \
                         patch.object(root, 'handlers', []), \
                         patch('sys.stderr', output), \
                         patch.object(main, 'PacedVisualizationHandler', side_effect=lambda pacer: pacer), \
                         patch.object(SimulationBuilder, 'add_handler', add_handler), \
                         patch('movable_external_uav_protocol.random.uniform', side_effect=rng.uniform):
                        main.main()
                    logs = output.getvalue()
                    if level in ('DEBUG', 'INFO'):
                        self.assertIn('enviada: externo', logs)
                        self.assertIn('recebida no externo', logs)
                    else:
                        self.assertNotIn('enviada: externo', logs)
                        self.assertNotIn('recebida no externo', logs)
                    self.assertNotIn('Finalizing simulation due to error', logs)
                    if level == 'DEBUG':
                        self.assertIn('encaminhando para', logs)
                    else:
                        self.assertNotIn('encaminhando para', logs)
                        self.assertNotIn('confirmada pelo externo', logs)
        finally:
            root.setLevel(old_level)


if __name__ == '__main__':
    unittest.main()
