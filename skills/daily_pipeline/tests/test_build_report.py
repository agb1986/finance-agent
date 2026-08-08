"""Tests for scripts/build_report.py and daily_pipeline.report."""

import json
import logging
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import build_report as build_report_script
from daily_pipeline import report as report_mod


@pytest.fixture(autouse=True)
def reset_logger():
    yield
    logging.getLogger("finance_agent").handlers.clear()


ARTICLE = {
    "rank": 1,
    "title": "Amazon surges",
    "summary": "Big move.",
    "url": "https://example.com/1",
    "source": "CNBC",
    "semantic_score": 0.91,
    "keyword_score": 0.5,
    "matched_keywords": ["amazon"],
}

VERDICT_FILE = {
    "symbol": "AMZN",
    "generated_at": "2026-08-01T09:00:00Z",
    "verdict": {
        "scorecard": {
            "bull": {
                "evidence_quality": 8,
                "rebuttal_validity": 7,
                "risk_adjusted_logic": 8,
                "internal_consistency": 9,
                "falsifiability": 6,
                "total": 38,
            },
            "bear": {
                "evidence_quality": 6,
                "rebuttal_validity": 6,
                "risk_adjusted_logic": 7,
                "internal_consistency": 8,
                "falsifiability": 5,
                "total": 32,
            },
        },
        "winner": "bull",
        "confidence": "medium",
        "strongest_bull_argument": "FCF growth.",
        "strongest_bear_argument": "Valuation.",
        "bull_fatal_flaw": "Ignores capex.",
        "bear_fatal_flaw": "No catalyst.",
        "key_unresolved_question": "Will AWS margins hold?",
        "verdict": "Bull wins.",
    },
}

PORTFOLIO = {
    "account_summary": {
        "currency": "GBP",
        "totalValue": 249.11,
        "investments": {"totalCost": 249.62, "unrealizedProfitLoss": -0.52},
    },
    "positions": [
        {
            "instrument": {"name": "Amazon"},
            "quantity": 0.7952,
            "currentPrice": 210.80,
            "walletImpact": {"totalCost": 124.81, "currentValue": 125.74},
        }
    ],
}


CRYPTO = {
    "fetched_at": "2026-08-08T07:00:00Z",
    "balances": [
        {
            "instrument_name": "USD",
            "total_cash_balance": "1250.50",
            "total_available_balance": "1000.00",
            "total_session_unrealized_pnl": "-12.34",
        }
    ],
    "position_balances": [
        {"instrument_name": "BTC", "quantity": "0.015", "market_value": "900.00"},
        {"instrument_name": "SOL", "quantity": "5", "market_value": "350.50"},
    ],
}


# ── section formatters ────────────────────────────────────────────────────────


class TestFormatters:
    def test_news_section_renders_article(self):
        result = report_mod.format_news_section([ARTICLE])
        assert "Amazon surges" in result
        assert "semantic: 0.91" in result
        assert "`amazon`" in result

    def test_news_section_empty(self):
        assert "No articles" in report_mod.format_news_section([])

    def test_tickers_section_table(self):
        result = report_mod.format_tickers_section([{"symbol": "AMZN", "mentions": 3}])
        assert "| AMZN | 3 |" in result

    def test_tickers_section_empty(self):
        assert "No known tickers" in report_mod.format_tickers_section([])

    def test_portfolio_section_renders_positions(self):
        result = report_mod.format_portfolio_section(PORTFOLIO)
        assert "**Total Value:** 249.11" in result
        assert "Amazon" in result
        assert "+0.93" in result

    def test_portfolio_section_none(self):
        assert "skipped or failed" in report_mod.format_portfolio_section(None)

    def test_crypto_section_renders_balance_and_positions(self):
        result = report_mod.format_crypto_section(CRYPTO)
        assert "**Currency:** USD" in result
        assert "**Cash balance:** 1250.50" in result
        assert "**Session unrealised PnL:** -12.34" in result
        assert "| BTC | 0.015 | 900.00 |" in result

    def test_crypto_section_positions_sorted_by_value(self):
        result = report_mod.format_crypto_section(CRYPTO)
        assert result.index("BTC") < result.index("SOL")

    def test_crypto_section_none(self):
        assert "skipped or failed" in report_mod.format_crypto_section(None)

    def test_crypto_section_no_positions(self):
        crypto = {**CRYPTO, "position_balances": []}
        assert "No open crypto positions" in report_mod.format_crypto_section(crypto)

    def test_crypto_section_bad_numbers_coerced(self):
        crypto = {
            "balances": [{"instrument_name": "USD", "total_cash_balance": "not-a-number"}],
            "position_balances": [],
        }
        result = report_mod.format_crypto_section(crypto)
        assert "**Cash balance:** 0.00" in result

    def test_verdict_section_scorecard(self):
        result = report_mod.format_verdict_section(VERDICT_FILE, cached=False)
        assert "### AMZN — 2026-08-01" in result
        assert "| **Total** | **38/50** | **32/50** |" in result
        assert "**Winner:** bull (medium confidence)" in result
        assert "cached" not in result

    def test_verdict_section_cached_note(self):
        result = report_mod.format_verdict_section(VERDICT_FILE, cached=True)
        assert "*(cached verdict)*" in result

    def test_verdict_section_malformed(self):
        bad = {"symbol": "AMZN", "verdict": {"raw": "...", "parse_error": "boom"}}
        assert "malformed" in report_mod.format_verdict_section(bad, cached=False)


# ── generate_summary ──────────────────────────────────────────────────────────

_USAGE = SimpleNamespace(
    input_tokens=1000,
    output_tokens=200,
    cache_read_input_tokens=0,
    cache_creation_input_tokens=0,
)


class TestGenerateSummary:
    def test_no_api_key_returns_none(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        assert report_mod.generate_summary("body") == (None, {})

    def test_returns_text_block(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        block = MagicMock(type="text", text="Summary here.")
        response = MagicMock(stop_reason="end_turn", content=[block], usage=_USAGE)
        client = MagicMock()
        client.messages.create.return_value = response
        with patch("anthropic.Anthropic", return_value=client):
            text, used = report_mod.generate_summary("body")
        assert text == "Summary here."
        assert used["claude-opus-5"]["input_tokens"] == 1000

    def test_refusal_returns_none(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        response = MagicMock(stop_reason="refusal", content=[], usage=_USAGE)
        client = MagicMock()
        client.messages.create.return_value = response
        with patch("anthropic.Anthropic", return_value=client):
            text, used = report_mod.generate_summary("body")
        # A refused call still burned tokens — report them even though the
        # summary is dropped.
        assert text is None
        assert used["claude-opus-5"]["calls"] == 1

    def test_exception_returns_none(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        with patch("anthropic.Anthropic", side_effect=RuntimeError("boom")):
            assert report_mod.generate_summary("body") == (None, {})


# ── build_report ──────────────────────────────────────────────────────────────


class TestBuildReport:
    def _fixture_paths(self, tmp_path):
        analysis = tmp_path / "analysis.json"
        analysis.write_text(json.dumps([ARTICLE]))
        tickers = tmp_path / "tickers.json"
        tickers.write_text(json.dumps([{"symbol": "AMZN", "mentions": 3}]))
        verdict = tmp_path / "verdict.json"
        verdict.write_text(json.dumps(VERDICT_FILE))
        return analysis, tickers, verdict

    def test_assembles_all_sections(self, tmp_path):
        analysis, tickers, verdict = self._fixture_paths(tmp_path)
        body = report_mod.build_report(
            date="2026-08-01",
            analysis_path=str(analysis),
            tickers_path=str(tickers),
            portfolio_path=None,
            verdicts=[{"path": str(verdict), "cached": False}],
            stages={"fetch_news": {"status": "done"}},
            with_summary=False,
        )
        assert "# Daily Finance Report — 2026-08-01" in body
        assert "## Top news" in body
        assert "### AMZN" in body
        assert "- fetch_news: done" in body

    def test_crypto_section_included_when_path_given(self, tmp_path):
        analysis, tickers, _ = self._fixture_paths(tmp_path)
        crypto = tmp_path / "crypto.json"
        crypto.write_text(json.dumps(CRYPTO))
        body = report_mod.build_report(
            date="2026-08-01",
            analysis_path=str(analysis),
            tickers_path=str(tickers),
            portfolio_path=None,
            crypto_path=str(crypto),
            verdicts=[],
            stages={},
            with_summary=False,
        )
        assert "## Crypto portfolio" in body
        assert "| BTC | 0.015 | 900.00 |" in body

    def test_no_verdicts_placeholder(self, tmp_path):
        analysis, tickers, _ = self._fixture_paths(tmp_path)
        body = report_mod.build_report(
            date="2026-08-01",
            analysis_path=str(analysis),
            tickers_path=str(tickers),
            portfolio_path=None,
            verdicts=[],
            stages={},
            with_summary=False,
        )
        assert "No trader runs today" in body

    def test_summary_inserted_at_top(self, tmp_path):
        analysis, tickers, _ = self._fixture_paths(tmp_path)
        with patch.object(report_mod, "generate_summary", return_value=("Exec summary.", {})):
            body = report_mod.build_report(
                date="2026-08-01",
                analysis_path=str(analysis),
                tickers_path=str(tickers),
                portfolio_path=None,
                verdicts=[],
                stages={},
                with_summary=True,
            )
        assert "## Summary\n\nExec summary." in body
        assert body.index("## Summary") < body.index("## Top news")


# ── script main ───────────────────────────────────────────────────────────────


class TestMain:
    def test_writes_report_and_prints_path(self, tmp_path, capsys):
        analysis = tmp_path / "analysis.json"
        analysis.write_text(json.dumps([ARTICLE]))
        tickers = tmp_path / "tickers.json"
        tickers.write_text(json.dumps([{"symbol": "AMZN", "mentions": 3}]))

        argv = [
            "build_report.py",
            "--analysis",
            str(analysis),
            "--tickers",
            str(tickers),
            "--no-summary",
        ]
        with (
            patch.object(build_report_script, "TMP_DIR", tmp_path / "out"),
            patch.object(sys, "argv", argv),
        ):
            build_report_script.main()

        output_path = Path(capsys.readouterr().out.strip())
        assert output_path.exists()
        assert "# Daily Finance Report" in output_path.read_text()
