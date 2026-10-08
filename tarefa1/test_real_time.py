import unittest
from unittest.mock import patch

from real_time_handler import RealTimeHandler, PacedVisualizationHandler


class RealTimeTest(unittest.TestCase):
    def test_factor_and_sleep_overshoot_do_not_accumulate_drift(self):
        for factor in (0.5, 1, 10):
            with self.subTest(factor=factor):
                clock = [100.0]

                def sleep_with_overshoot(duration):
                    clock[0] += duration + 0.015

                with patch('real_time_handler.time.perf_counter', side_effect=lambda: clock[0]), \
                     patch('real_time_handler.time.sleep', side_effect=sleep_with_overshoot):
                    handler = RealTimeHandler(factor)
                    handler.initialize()
                    for index in range(1, 201):
                        handler.after_simulation_step(index, index * 0.01)
                    self.assertAlmostEqual(clock[0] - 100, 2 / factor, delta=0.016)

    def test_processing_time_is_deducted_from_wait(self):
        handler = RealTimeHandler(10)
        with patch('real_time_handler.time.perf_counter', side_effect=[100, 100.05]), \
             patch('real_time_handler.time.sleep') as sleep:
            handler.initialize()
            handler.after_simulation_step(1, 1)
            self.assertAlmostEqual(sleep.call_args.args[0], 0.05)

    def test_invalid_factor(self):
        for factor in (0, -1, float('nan'), float('inf')):
            with self.subTest(factor=factor), self.assertRaises(ValueError):
                RealTimeHandler(factor)

    def test_browser_pause_shifts_real_time_origin(self):
        # Evita abrir servidor e processos para testar o desconto da pausa.
        visualization = PacedVisualizationHandler.__new__(PacedVisualizationHandler)
        visualization.pacer = RealTimeHandler(10)
        visualization.pacer.started_at = 100
        visualization._visualization_state = {'paused': True}
        with patch('real_time_handler.time.perf_counter', side_effect=[101, 106]), \
             patch('real_time_handler.VisualizationHandler._report_information'):
            visualization._report_information()
        self.assertEqual(visualization.pacer.started_at, 105)


if __name__ == '__main__':
    unittest.main()
