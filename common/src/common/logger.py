"""
Shared logger for all finance-agent scripts.

Usage in a script:
    from common.args import base_parser
    from common.logger import setup, get_logger

    parser = argparse.ArgumentParser(parents=[base_parser()])
    args = parser.parse_args()
    setup(args.debug)

    logger = get_logger()
    logger.debug("starting up")
    logger.error("something went wrong")

Log format:
    LEVEL::timestamp::script::function::message

Levels are color-coded. DEBUG+ is shown only when debug=True; ERROR+ always.
"""

import logging
import sys
from pathlib import Path

_COLORS: dict[str, str] = {
    "DEBUG": "\033[36m",  # cyan
    "INFO": "\033[32m",  # green
    "WARNING": "\033[33m",  # yellow
    "ERROR": "\033[31m",  # red
    "CRITICAL": "\033[35m",  # magenta
    "RESET": "\033[0m",
}

_logger = logging.getLogger("finance_agent")
_logger.addHandler(logging.NullHandler())


class _Formatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        color = _COLORS.get(record.levelname, "")
        reset = _COLORS["RESET"]
        level = f"{color}{record.levelname}{reset}"
        timestamp = self.formatTime(record, "%Y-%m-%d %H:%M:%S")
        script = Path(sys.argv[0]).stem
        return f"{level}::{timestamp}::{script}::{record.funcName}::{record.getMessage()}"


def setup(debug: bool) -> logging.Logger:
    """Configure the logger. Call once at script startup after parsing args."""
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(_Formatter())
    handler.setLevel(logging.DEBUG if debug else logging.ERROR)
    _logger.addHandler(handler)
    _logger.setLevel(logging.DEBUG)
    return _logger


def get_logger() -> logging.Logger:
    """Return the shared logger. setup() must be called first."""
    return _logger
