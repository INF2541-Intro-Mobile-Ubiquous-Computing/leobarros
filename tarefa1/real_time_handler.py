"""Controla a reprodução sem acumular o atraso de cada pequena espera."""

import math
import time

from gradysim.simulator.handler.interface import INodeHandler
from gradysim.simulator.handler.visualization import VisualizationHandler


class RealTimeHandler(INodeHandler):
    def __init__(self, factor):
        if not math.isfinite(factor) or factor <= 0:
            raise ValueError('REAL_TIME deve ser positivo e finito.')
        self.factor = factor

    @staticmethod
    def get_label():
        return 'real_time'

    def inject(self, event_loop):
        pass

    def register_node(self, node):
        pass

    def initialize(self):
        self.started_at = time.perf_counter()

    def after_simulation_step(self, iteration, timestamp):
        deadline = self.started_at + timestamp / self.factor
        remaining = deadline - time.perf_counter()
        if remaining > 0:
            time.sleep(remaining)


class PacedVisualizationHandler(VisualizationHandler):
    """Desconta pausas do navegador para não acelerar ao retomar a execução."""

    def __init__(self, pacer):
        super().__init__()
        self.pacer = pacer

    def _report_information(self):
        paused = self._visualization_state['paused']
        started = time.perf_counter()
        super()._report_information()
        if paused:
            self.pacer.started_at += time.perf_counter() - started
