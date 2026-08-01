"""Tests for scripts/send_email.py and daily_pipeline.emailer."""

import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import send_email as send_email_script
from daily_pipeline import emailer

SMTP_ENV = {
    "SMTP_HOST": "smtp.example.com",
    "SMTP_USER": "user@example.com",
    "SMTP_PASSWORD": "secret",
    "REPORT_TO": "me@example.com",
}


@pytest.fixture(autouse=True)
def reset_logger():
    yield
    logging.getLogger("finance_agent").handlers.clear()


@pytest.fixture
def smtp_env(monkeypatch):
    for key, value in SMTP_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("SMTP_PORT", raising=False)
    monkeypatch.delenv("REPORT_FROM", raising=False)


# ── load_smtp_config ──────────────────────────────────────────────────────────


class TestLoadSmtpConfig:
    def test_reads_env(self, smtp_env):
        config = emailer.load_smtp_config()
        assert config["host"] == "smtp.example.com"
        assert config["port"] == 587
        assert config["from_addr"] == "user@example.com"

    def test_missing_vars_named_in_error(self, monkeypatch):
        for key in SMTP_ENV:
            monkeypatch.delenv(key, raising=False)
        with pytest.raises(RuntimeError, match="SMTP_HOST.*REPORT_TO"):
            emailer.load_smtp_config()

    def test_custom_port_and_from(self, smtp_env, monkeypatch):
        monkeypatch.setenv("SMTP_PORT", "465")
        monkeypatch.setenv("REPORT_FROM", "reports@example.com")
        config = emailer.load_smtp_config()
        assert config["port"] == 465
        assert config["from_addr"] == "reports@example.com"


# ── build_message ─────────────────────────────────────────────────────────────


class TestBuildMessage:
    def test_multipart_with_html_and_plain(self):
        message = emailer.build_message("Subject", "# Hello", "a@x.com", "b@x.com")
        assert message["Subject"] == "Subject"
        parts = message.get_payload()
        assert parts[0].get_content_type() == "text/plain"
        assert parts[1].get_content_type() == "text/html"
        assert "<h1>Hello</h1>" in parts[1].get_payload()


# ── send_report ───────────────────────────────────────────────────────────────


class TestSendReport:
    def test_sends_via_starttls(self, smtp_env):
        smtp = MagicMock()
        with patch.object(emailer.smtplib, "SMTP") as smtp_cls:
            smtp_cls.return_value.__enter__.return_value = smtp
            emailer.send_report("Subject", "body")
        smtp.starttls.assert_called_once()
        smtp.login.assert_called_once_with("user@example.com", "secret")
        smtp.send_message.assert_called_once()

    def test_missing_config_raises(self, monkeypatch):
        for key in SMTP_ENV:
            monkeypatch.delenv(key, raising=False)
        with pytest.raises(RuntimeError):
            emailer.send_report("Subject", "body")


# ── script main ───────────────────────────────────────────────────────────────


class TestMain:
    def test_sends_report_file(self, tmp_path, capsys):
        report = tmp_path / "report.md"
        report.write_text("# Report")
        argv = ["send_email.py", "--report", str(report), "--subject", "Test subject"]
        with (
            patch.object(send_email_script, "send_report") as send_mock,
            patch.object(sys, "argv", argv),
        ):
            send_email_script.main()
        send_mock.assert_called_once_with("Test subject", "# Report")
        assert "sent: Test subject" in capsys.readouterr().out

    def test_missing_report_exits_nonzero(self, tmp_path):
        argv = ["send_email.py", "--report", str(tmp_path / "nope.md")]
        with patch.object(sys, "argv", argv), pytest.raises(SystemExit) as excinfo:
            send_email_script.main()
        assert excinfo.value.code == 1

    def test_delivery_failure_exits_nonzero(self, tmp_path):
        report = tmp_path / "report.md"
        report.write_text("# Report")
        argv = ["send_email.py", "--report", str(report)]
        with (
            patch.object(send_email_script, "send_report", side_effect=RuntimeError("boom")),
            patch.object(sys, "argv", argv),
            pytest.raises(SystemExit) as excinfo,
        ):
            send_email_script.main()
        assert excinfo.value.code == 1
