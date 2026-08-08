"""Tests for scripts/run_daily.py, daily_pipeline.runner, and daily_pipeline.config."""

import json
import logging
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import run_daily as run_daily_script
from daily_pipeline import runner
from daily_pipeline.config import DEFAULTS, load_config
from daily_pipeline.runner import (
    StageError,
    acquire_lock,
    build_market_context,
    find_cached_verdict,
    load_manifest,
    plan,
    prune_old_runs,
    record_stage,
    run_pipeline,
    run_script,
    run_trader,
    stage_done,
)


@pytest.fixture(autouse=True)
def reset_logger():
    yield
    logging.getLogger("finance_agent").handlers.clear()


# ── config ────────────────────────────────────────────────────────────────────


class TestLoadConfig:
    def test_missing_file_returns_defaults(self, tmp_path):
        config = load_config(tmp_path / "nope.yaml")
        assert config == DEFAULTS

    def test_partial_file_merges_over_defaults(self, tmp_path):
        path = tmp_path / "pipeline.yaml"
        path.write_text("trader:\n  max_runs: 2\n")
        config = load_config(path)
        assert config["trader"]["max_runs"] == 2
        assert config["trader"]["rounds"] == 2
        assert config["news"]["hours"] == 24

    def test_scalar_override(self, tmp_path):
        path = tmp_path / "pipeline.yaml"
        path.write_text("retention_days: 7\n")
        assert load_config(path)["retention_days"] == 7

    def test_repo_config_loads(self):
        config = load_config()
        assert config["tickers"]["top_n"] == 5


# ── run_script ────────────────────────────────────────────────────────────────


class TestRunScript:
    def test_returns_first_stdout_line(self):
        completed = MagicMock(returncode=0, stdout="path/to/out.json\nextra report\n", stderr="")
        with patch.object(runner.subprocess, "run", return_value=completed):
            assert run_script("some/script.py") == "path/to/out.json"

    def test_nonzero_exit_raises_with_stderr_tail(self):
        completed = MagicMock(returncode=1, stdout="", stderr="line1\nboom\n")
        with patch.object(runner.subprocess, "run", return_value=completed):
            with pytest.raises(StageError, match="boom"):
                run_script("some/script.py")

    def test_timeout_raises(self):
        with patch.object(
            runner.subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired(cmd="x", timeout=1),
        ):
            with pytest.raises(StageError, match="timed out"):
                run_script("some/script.py", timeout=1)

    def test_empty_stdout_raises(self):
        completed = MagicMock(returncode=0, stdout="", stderr="")
        with patch.object(runner.subprocess, "run", return_value=completed):
            with pytest.raises(StageError, match="no output path"):
                run_script("some/script.py")


# ── manifest helpers ──────────────────────────────────────────────────────────


class TestManifest:
    def test_load_initialises_when_missing(self, tmp_path):
        assert load_manifest(tmp_path) == {"stages": {}, "trader": {}}

    def test_record_and_reload(self, tmp_path):
        manifest = load_manifest(tmp_path)
        record_stage(tmp_path, manifest, "fetch_news", "done", "out.json")
        reloaded = load_manifest(tmp_path)
        assert reloaded["stages"]["fetch_news"]["status"] == "done"

    def test_stage_done_requires_existing_output(self, tmp_path):
        manifest = load_manifest(tmp_path)
        record_stage(tmp_path, manifest, "s", "done", str(tmp_path / "gone.json"))
        assert not stage_done(manifest, "s")
        (tmp_path / "gone.json").touch()
        assert stage_done(manifest, "s")

    def test_stage_done_without_output_path(self, tmp_path):
        manifest = load_manifest(tmp_path)
        record_stage(tmp_path, manifest, "s", "done")
        assert stage_done(manifest, "s")

    def test_stage_not_done_when_failed_or_absent(self, tmp_path):
        manifest = load_manifest(tmp_path)
        assert not stage_done(manifest, "missing")
        record_stage(tmp_path, manifest, "s", "failed")
        assert not stage_done(manifest, "s")


# ── locking and retention ─────────────────────────────────────────────────────


class TestLockAndPrune:
    def test_acquire_and_release(self, tmp_path):
        lock = acquire_lock(tmp_path)
        assert lock.exists()

    def test_fresh_lock_blocks(self, tmp_path):
        acquire_lock(tmp_path)
        with pytest.raises(StageError, match="another run in progress"):
            acquire_lock(tmp_path)

    def test_stale_lock_replaced(self, tmp_path):
        lock = acquire_lock(tmp_path)
        stale = time.time() - runner.LOCK_MAX_AGE - 10
        import os

        os.utime(lock, (stale, stale))
        assert acquire_lock(tmp_path).exists()

    def test_concurrent_lock_creation_raises(self, tmp_path):
        # Simulate the loser of the exists-check race: the file appears between
        # the check and the atomic create.
        with patch.object(Path, "open", side_effect=FileExistsError):
            with pytest.raises(StageError, match="another run won"):
                acquire_lock(tmp_path)

    def test_prune_removes_only_old_runs(self, tmp_path):
        (tmp_path / "run_20260701").mkdir()
        (tmp_path / "run_20260731").mkdir()
        (tmp_path / "not_a_run").mkdir()
        removed = prune_old_runs(tmp_path, retention_days=14, now=datetime(2026, 8, 1))
        assert removed == 1
        assert not (tmp_path / "run_20260701").exists()
        assert (tmp_path / "run_20260731").exists()
        assert (tmp_path / "not_a_run").exists()


# ── verdict cache + trader ────────────────────────────────────────────────────


class TestVerdictCache:
    def test_finds_newest_within_age(self, tmp_path):
        (tmp_path / "verdict_AMZN_20260730_090000.json").touch()
        (tmp_path / "verdict_AMZN_20260731_090000.json").touch()
        result = find_cached_verdict("AMZN", 3, tmp_path, now=datetime(2026, 8, 1))
        assert result.name == "verdict_AMZN_20260731_090000.json"

    def test_too_old_ignored(self, tmp_path):
        (tmp_path / "verdict_AMZN_20260701_090000.json").touch()
        assert find_cached_verdict("AMZN", 3, tmp_path, now=datetime(2026, 8, 1)) is None

    def test_other_symbol_ignored(self, tmp_path):
        (tmp_path / "verdict_TSLA_20260731_090000.json").touch()
        assert find_cached_verdict("AMZN", 3, tmp_path, now=datetime(2026, 8, 1)) is None

    def test_missing_dir(self, tmp_path):
        assert find_cached_verdict("AMZN", 3, tmp_path / "nope") is None

    def test_run_trader_chains_stages(self):
        with patch.object(
            runner, "run_script", side_effect=["panel.json", "debate.json", "verdict.json"]
        ) as run_mock:
            assert run_trader("AMZN", rounds=2) == "verdict.json"
        assert run_mock.call_count == 3
        assert run_mock.call_args_list[0].args[1] == ["--symbol", "AMZN"]
        assert run_mock.call_args_list[1].args[1] == ["--input", "panel.json", "--rounds", "2"]

    def test_run_trader_passes_context_file_to_panel(self):
        with patch.object(
            runner, "run_script", side_effect=["panel.json", "debate.json", "verdict.json"]
        ) as run_mock:
            run_trader("AMZN", rounds=2, context_file="ctx.md")
        assert run_mock.call_args_list[0].args[1] == [
            "--symbol",
            "AMZN",
            "--context-file",
            "ctx.md",
        ]


# ── market context ────────────────────────────────────────────────────────────

QUOTE = {
    "symbol": "AMZN",
    "fetched_at": "2026-08-08T07:00:00Z",
    "name": "Amazon.com, Inc.",
    "price": 185.5,
    "currency": "USD",
    "change": 1.2,
    "change_percent": 0.65,
    "volume": 1000,
    "market_cap": 2_000_000,
    "pe_ratio": 40.5,
    "week_52_high": 200.0,
    "week_52_low": 140.0,
}

HISTORY = {
    "symbol": "AMZN",
    "period": "6mo",
    "fetched_at": "2026-08-08T07:00:00Z",
    "bars": [
        {
            "date": f"2026-07-{day:02d}",
            "open": 180.0 + day,
            "high": 181.0 + day,
            "low": 179.0 + day,
            "close": 180.5 + day,
            "volume": 100 + day,
        }
        for day in range(1, 26)
    ],
}


class TestBuildMarketContext:
    def _paths(self, tmp_path):
        quote_path = tmp_path / "quote.json"
        quote_path.write_text(json.dumps(QUOTE))
        history_path = tmp_path / "history.json"
        history_path.write_text(json.dumps(HISTORY))
        return str(quote_path), str(history_path)

    def test_writes_context_file(self, tmp_path):
        quote_path, history_path = self._paths(tmp_path)
        with patch.object(runner, "run_script", side_effect=[quote_path, history_path]) as run_mock:
            result = build_market_context("AMZN", tmp_path, "6mo")
        assert result == tmp_path / "context_AMZN.md"
        content = result.read_text()
        assert "AMZN" in content
        assert "185.50" in content
        assert run_mock.call_args_list[1].args[1] == ["--symbol", "AMZN", "--period", "6mo"]

    def test_fetch_failure_returns_none(self, tmp_path):
        with patch.object(runner, "run_script", side_effect=StageError("yahoo down")):
            assert build_market_context("AMZN", tmp_path, "6mo") is None


# ── plan ──────────────────────────────────────────────────────────────────────


class TestPlan:
    def test_reflects_config(self):
        steps = plan(DEFAULTS)
        assert any("--hours 24" in s for s in steps)
        assert any("max 2 runs" in s for s in steps)


# ── run_pipeline ──────────────────────────────────────────────────────────────


ARTICLES = [
    {
        "rank": 1,
        "title": "Amazon surges",
        "summary": "Big move.",
        "url": "u1",
        "source": "CNBC",
        "semantic_score": 0.9,
        "keyword_score": 0.5,
        "matched_keywords": [],
    }
]


@pytest.fixture
def pipeline_env(tmp_path, monkeypatch):
    """Isolated TMP_DIR, fixture artifacts, and a run_script stub."""
    for key in ["TRADING_212_API_KEY", "CRYPTO_API_KEY", "ANTHROPIC_API_KEY"]:
        monkeypatch.delenv(key, raising=False)

    news_path = tmp_path / "news.json"
    news_path.write_text(json.dumps(ARTICLES))
    analysis_path = tmp_path / "analysis.json"
    analysis_path.write_text(json.dumps(ARTICLES))
    verdict_path = tmp_path / "verdict_AMZN_20260801_090000.json"
    verdict_path.write_text(
        json.dumps({"symbol": "AMZN", "generated_at": "2026-08-01T09:00:00Z", "verdict": {}})
    )
    quote_path = tmp_path / "quote.json"
    quote_path.write_text(json.dumps(QUOTE))
    history_path = tmp_path / "history.json"
    history_path.write_text(json.dumps(HISTORY))

    outputs = {
        "skills/financial_news/scripts/fetch_news.py": str(news_path),
        "skills/financial_news/scripts/analyze_news.py": str(analysis_path),
        "skills/check_stock/scripts/fetch_quote.py": str(quote_path),
        "skills/check_stock/scripts/fetch_history.py": str(history_path),
    }

    def fake_run_script(script, args=None, timeout=None):
        return outputs[script]

    monkeypatch.setattr(runner, "TMP_DIR", tmp_path / "pipeline_tmp")
    monkeypatch.setattr(runner, "run_script", fake_run_script)
    monkeypatch.setattr(runner.tickers_mod, "load_ticker_map", lambda path=None: {"amazon": "AMZN"})
    return {"tmp": tmp_path, "verdict": verdict_path, "outputs": outputs}


class TestRunPipeline:
    def test_full_run_with_cached_verdict(self, pipeline_env):
        with patch.object(runner, "find_cached_verdict", return_value=pipeline_env["verdict"]):
            manifest = run_pipeline(DEFAULTS, date="20260801", skip_email=True, with_summary=False)
        stages = manifest["stages"]
        assert stages["fetch_news"]["status"] == "done"
        assert stages["analyze_news"]["status"] == "done"
        assert stages["extract_tickers"]["status"] == "done"
        assert stages["stock_portfolio"]["status"] == "skipped"
        assert stages["crypto_portfolio"]["status"] == "skipped"
        assert stages["send_email"]["status"] == "skipped"
        assert manifest["trader"]["AMZN"]["cached"] is True
        assert Path(manifest["report"]).exists()
        assert "AMZN" in Path(manifest["report"]).read_text()

    def test_trader_failure_recorded_and_run_continues(self, pipeline_env):
        with (
            patch.object(runner, "find_cached_verdict", return_value=None),
            patch.object(runner, "run_trader", side_effect=StageError("panel died")),
        ):
            manifest = run_pipeline(DEFAULTS, date="20260801", skip_email=True, with_summary=False)
        assert manifest["trader"]["AMZN"]["status"] == "failed"
        assert Path(manifest["report"]).exists()

    def test_resume_skips_completed_stages(self, pipeline_env):
        calls = []
        original = runner.run_script

        def counting_run_script(script, args=None, timeout=None):
            calls.append(script)
            return original(script, args, timeout)

        with (
            patch.object(runner, "find_cached_verdict", return_value=pipeline_env["verdict"]),
            patch.object(runner, "run_script", counting_run_script),
        ):
            run_pipeline(DEFAULTS, date="20260801", skip_email=True, with_summary=False)
            first_count = len(calls)
            run_pipeline(DEFAULTS, date="20260801", skip_email=True, with_summary=False)
        assert first_count == 2
        assert len(calls) == 2  # nothing re-ran on resume

    def test_trader_grounded_with_market_context(self, pipeline_env):
        with (
            patch.object(runner, "find_cached_verdict", return_value=None),
            patch.object(
                runner, "run_trader", return_value=str(pipeline_env["verdict"])
            ) as trader_mock,
        ):
            manifest = run_pipeline(DEFAULTS, date="20260801", skip_email=True, with_summary=False)

        context_file = trader_mock.call_args.kwargs["context_file"]
        assert context_file is not None
        assert Path(context_file).exists()
        assert "185.50" in Path(context_file).read_text()
        assert manifest["trader"]["AMZN"]["context"] == context_file

    def test_trader_runs_ungrounded_when_market_data_fails(self, pipeline_env):
        with (
            patch.object(runner, "find_cached_verdict", return_value=None),
            patch.object(runner, "build_market_context", return_value=None),
            patch.object(
                runner, "run_trader", return_value=str(pipeline_env["verdict"])
            ) as trader_mock,
        ):
            manifest = run_pipeline(DEFAULTS, date="20260801", skip_email=True, with_summary=False)

        assert trader_mock.call_args.kwargs["context_file"] is None
        assert manifest["trader"]["AMZN"]["status"] == "done"

    def test_email_sent_when_configured(self, pipeline_env):
        with (
            patch.object(runner, "find_cached_verdict", return_value=None),
            patch.object(runner, "run_trader", return_value=str(pipeline_env["verdict"])),
            patch.object(runner, "send_report") as send_mock,
        ):
            manifest = run_pipeline(DEFAULTS, date="20260801", with_summary=False)
        send_mock.assert_called_once()
        assert manifest["stages"]["send_email"]["status"] == "done"

    def test_email_failure_raises_stage_error(self, pipeline_env):
        with (
            patch.object(runner, "find_cached_verdict", return_value=None),
            patch.object(runner, "run_trader", return_value=str(pipeline_env["verdict"])),
            patch.object(runner, "send_report", side_effect=RuntimeError("smtp down")),
        ):
            with pytest.raises(StageError, match="email delivery failed"):
                run_pipeline(DEFAULTS, date="20260801", with_summary=False)

    def test_max_trader_runs_caps_symbols(self, pipeline_env):
        with patch.object(runner, "find_cached_verdict", return_value=None):
            with patch.object(runner, "run_trader") as trader_mock:
                trader_mock.return_value = str(pipeline_env["verdict"])
                run_pipeline(
                    DEFAULTS,
                    date="20260801",
                    max_trader_runs=0,
                    skip_email=True,
                    with_summary=False,
                )
        trader_mock.assert_not_called()

    def test_lock_released_after_run(self, pipeline_env):
        with patch.object(runner, "find_cached_verdict", return_value=None):
            run_pipeline(
                DEFAULTS, date="20260801", max_trader_runs=0, skip_email=True, with_summary=False
            )
        assert not (runner.TMP_DIR / "run_20260801" / ".lock").exists()


# ── script main ───────────────────────────────────────────────────────────────


class TestMain:
    def test_dry_run_prints_plan(self, capsys):
        with patch.object(sys, "argv", ["run_daily.py", "--dry-run"]):
            run_daily_script.main()
        out = capsys.readouterr().out
        assert "dry run" in out
        assert "fetch_news" in out

    def test_success_prints_report_path(self, capsys):
        manifest = {"report": "tmp/run_20260801/report.md"}
        argv = ["run_daily.py", "--skip-email"]
        with (
            patch.object(run_daily_script, "run_pipeline", return_value=manifest) as run_mock,
            patch.object(sys, "argv", argv),
        ):
            run_daily_script.main()
        assert "report.md" in capsys.readouterr().out
        assert run_mock.call_args.kwargs["skip_email"] is True

    def test_stage_error_exits_nonzero_and_sends_alert(self):
        with (
            patch.object(run_daily_script, "run_pipeline", side_effect=StageError("boom")),
            patch.object(run_daily_script, "send_report") as send_mock,
            patch.object(sys, "argv", ["run_daily.py"]),
            pytest.raises(SystemExit) as excinfo,
        ):
            run_daily_script.main()
        assert excinfo.value.code == 1
        subject, body = send_mock.call_args.args
        assert "FAILED" in subject
        assert "boom" in body

    def test_alert_failure_does_not_mask_exit_code(self):
        with (
            patch.object(run_daily_script, "run_pipeline", side_effect=StageError("boom")),
            patch.object(
                run_daily_script, "send_report", side_effect=RuntimeError("smtp not configured")
            ),
            patch.object(sys, "argv", ["run_daily.py"]),
            pytest.raises(SystemExit) as excinfo,
        ):
            run_daily_script.main()
        assert excinfo.value.code == 1

    def test_success_sends_no_alert(self, capsys):
        manifest = {"report": "tmp/run_20260801/report.md"}
        with (
            patch.object(run_daily_script, "run_pipeline", return_value=manifest),
            patch.object(run_daily_script, "send_report") as send_mock,
            patch.object(sys, "argv", ["run_daily.py", "--skip-email"]),
        ):
            run_daily_script.main()
        send_mock.assert_not_called()
