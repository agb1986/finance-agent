"""Tests for common.logger."""

import logging

import common.logger as logger_mod
import pytest
from common.logger import get_logger, setup


@pytest.fixture(autouse=True)
def reset_logger():
    yield
    log = logging.getLogger("finance_agent")
    log.handlers.clear()
    # Restore the NullHandler that the module adds at import time
    log.addHandler(logging.NullHandler())


class TestSetup:
    def test_returns_logger(self):
        log = setup(debug=False)
        assert isinstance(log, logging.Logger)
        assert log.name == "finance_agent"

    def test_debug_false_sets_error_level_on_handler(self):
        setup(debug=False)
        log = logging.getLogger("finance_agent")
        stream_handlers = [
            h
            for h in log.handlers
            if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.NullHandler)
        ]
        assert len(stream_handlers) == 1
        assert stream_handlers[0].level == logging.ERROR

    def test_debug_true_sets_debug_level_on_handler(self):
        setup(debug=True)
        log = logging.getLogger("finance_agent")
        stream_handlers = [
            h
            for h in log.handlers
            if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.NullHandler)
        ]
        assert len(stream_handlers) == 1
        assert stream_handlers[0].level == logging.DEBUG

    def test_logger_level_always_debug(self):
        setup(debug=False)
        log = logging.getLogger("finance_agent")
        assert log.level == logging.DEBUG

    def test_handler_uses_custom_formatter(self):
        setup(debug=False)
        log = logging.getLogger("finance_agent")
        stream_handlers = [
            h
            for h in log.handlers
            if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.NullHandler)
        ]
        assert isinstance(stream_handlers[0].formatter, logger_mod._Formatter)


class TestGetLogger:
    def test_returns_finance_agent_logger(self):
        log = get_logger()
        assert log.name == "finance_agent"

    def test_same_instance_as_setup(self):
        log1 = setup(debug=False)
        log2 = get_logger()
        assert log1 is log2


class TestFormatter:
    def test_format_includes_level(self, capsys):
        setup(debug=True)
        log = get_logger()
        log.debug("hello")
        captured = capsys.readouterr()
        assert "DEBUG" in captured.err

    def test_format_includes_message(self, capsys):
        setup(debug=True)
        log = get_logger()
        log.debug("my test message")
        captured = capsys.readouterr()
        assert "my test message" in captured.err

    def test_error_visible_without_debug(self, capsys):
        setup(debug=False)
        log = get_logger()
        log.error("something failed")
        captured = capsys.readouterr()
        assert "something failed" in captured.err

    def test_debug_hidden_without_debug_flag(self, capsys):
        setup(debug=False)
        log = get_logger()
        log.debug("hidden message")
        captured = capsys.readouterr()
        assert "hidden message" not in captured.err

    def test_format_separator_style(self, capsys):
        setup(debug=True)
        log = get_logger()
        log.info("sep test")
        captured = capsys.readouterr()
        # format: LEVEL::timestamp::script::function::message
        assert "::" in captured.err
