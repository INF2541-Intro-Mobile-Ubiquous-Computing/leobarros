"""Logging setup for the application and GrADyS-SIM status messages."""
import logging
from pathlib import Path

from gradysim.simulator.log import SimulationFormatter


class SimulatorStatusFilter(logging.Filter):
    """Expose library status output only at DEBUG, retaining runtime errors."""

    def filter(self, record: logging.LogRecord) -> bool:
        lifecycle_message = record.getMessage()
        if lifecycle_message in (
            "[--------- Simulation started ---------]",
            "[--------- Simulation finished ---------]",
        ) or lifecycle_message.startswith("Real time elapsed:"):
            return True
        if 'gradysim' in Path(record.pathname).parts and record.levelno < logging.WARNING:
            record.levelno = logging.DEBUG
            record.levelname = 'DEBUG'
            return logging.getLogger().isEnabledFor(logging.DEBUG)
        return True


def configure_logging(level: str) -> None:
    """Apply after simulator build as well, since it installs new handlers."""
    root = logging.getLogger()
    root.setLevel(level)
    # Module-level logging calls can install a default StreamHandler before
    # GrADyS-SIM adds its own. Keep the newest simulator console formatter,
    # including when another simulation is built in the same process.
    # Exact type matching deliberately preserves FileHandler and custom sinks.
    console_handlers = [handler for handler in root.handlers
                        if type(handler) is logging.StreamHandler]
    simulator_handlers = [handler for handler in console_handlers
                          if isinstance(handler.formatter, SimulationFormatter)]
    if simulator_handlers:
        selected = simulator_handlers[-1]
        for handler in console_handlers:
            if handler is not selected:
                root.removeHandler(handler)
                handler.close()
    for handler in root.handlers:
        if not any(isinstance(item, SimulatorStatusFilter) for item in handler.filters):
            handler.addFilter(SimulatorStatusFilter())
