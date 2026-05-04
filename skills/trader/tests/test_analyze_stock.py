"""Tests for analyze_stock.py and trader.analyzer."""

import importlib.util
import logging
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── load the thin script ──────────────────────────────────────────────────────
_spec = importlib.util.spec_from_file_location(
    "trader_analyze_stock",
    Path(__file__).parent.parent / "scripts" / "analyze_stock.py",
)
analyze_stock = importlib.util.module_from_spec(_spec)
sys.modules["trader_analyze_stock"] = analyze_stock
_spec.loader.exec_module(analyze_stock)
from trader.analyzer import render_report, run_analysis  # noqa: E402, I001


# ── helpers ───────────────────────────────────────────────────────────────────


def _make_final_state(
    market_report: str = "Market is bullish.",
    sentiment_report: str = "Social sentiment positive.",
    news_report: str = "Recent news favourable.",
    fundamentals_report: str = "Strong revenue growth.",
    trader_investment_plan: str = "Buy NVDA on dips.",
    final_trade_decision: str = "BUY — strong fundamentals.",
    bull_history: str = "Bull argument here.",
    bear_history: str = "Bear argument here.",
    invest_judge: str = "Bull wins.",
    aggressive_history: str = "Aggressive view.",
    conservative_history: str = "Conservative view.",
    neutral_history: str = "Neutral view.",
    risk_judge: str = "Moderate risk.",
) -> MagicMock:
    """Return a MagicMock with the same attribute layout as AgentState."""
    state = MagicMock()
    state.market_report = market_report
    state.sentiment_report = sentiment_report
    state.news_report = news_report
    state.fundamentals_report = fundamentals_report
    state.trader_investment_plan = trader_investment_plan
    state.final_trade_decision = final_trade_decision

    invest = MagicMock()
    invest.bull_history = bull_history
    invest.bear_history = bear_history
    invest.judge_decision = invest_judge
    state.investment_debate_state = invest

    risk = MagicMock()
    risk.aggressive_history = aggressive_history
    risk.conservative_history = conservative_history
    risk.neutral_history = neutral_history
    risk.judge_decision = risk_judge
    state.risk_debate_state = risk

    return state


# ── fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def reset_logger():
    yield
    logging.getLogger("finance_agent").handlers.clear()


@pytest.fixture()
def sample_result() -> dict:
    return {
        "symbol": "NVDA",
        "trade_date": "2026-01-15",
        "analyzed_at": "2026-01-15T10:00:00Z",
        "decision": "BUY",
        "market_report": "Market conditions are bullish.",
        "sentiment_report": "Social sentiment is positive.",
        "news_report": "Recent news is favourable.",
        "fundamentals_report": "Strong revenue growth.",
        "investment_debate": {
            "bull_history": "Bull argument here.",
            "bear_history": "Bear argument here.",
            "judge_decision": "Bull wins.",
        },
        "risk_debate": {
            "aggressive_history": "Aggressive view.",
            "conservative_history": "Conservative view.",
            "neutral_history": "Neutral view.",
            "judge_decision": "Moderate risk.",
        },
        "trader_plan": "Buy NVDA on dips.",
        "final_decision": "BUY — strong fundamentals and bullish sentiment.",
    }


# ── run_analysis ──────────────────────────────────────────────────────────────


class TestRunAnalysis:
    def test_raises_when_api_key_missing(self):
        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(OSError, match="ANTHROPIC_API_KEY"):
                run_analysis("NVDA", "2026-01-15")

    def test_returns_expected_keys(self):
        mock_ta = MagicMock()
        mock_ta.propagate.return_value = (_make_final_state(), "BUY")

        with (
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}),
            patch("trader.analyzer.TradingAgentsGraph", return_value=mock_ta),
        ):
            result = run_analysis("NVDA", "2026-01-15")

        expected_keys = {
            "symbol",
            "trade_date",
            "analyzed_at",
            "decision",
            "market_report",
            "sentiment_report",
            "news_report",
            "fundamentals_report",
            "investment_debate",
            "risk_debate",
            "trader_plan",
            "final_decision",
        }
        assert set(result.keys()) == expected_keys

    def test_symbol_and_date_passed_to_propagate(self):
        mock_ta = MagicMock()
        mock_ta.propagate.return_value = (_make_final_state(), "HOLD")

        with (
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}),
            patch("trader.analyzer.TradingAgentsGraph", return_value=mock_ta),
        ):
            run_analysis("TSLA", "2026-03-01")

        mock_ta.propagate.assert_called_once_with("TSLA", "2026-03-01")

    def test_decision_returned_from_propagate(self):
        mock_ta = MagicMock()
        mock_ta.propagate.return_value = (_make_final_state(), "SELL")

        with (
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}),
            patch("trader.analyzer.TradingAgentsGraph", return_value=mock_ta),
        ):
            result = run_analysis("NVDA", "2026-01-15")

        assert result["decision"] == "SELL"

    def test_reports_extracted_from_state(self):
        mock_ta = MagicMock()
        state = _make_final_state(
            market_report="Bullish conditions.",
            fundamentals_report="Strong revenue.",
            trader_investment_plan="Buy on dips.",
        )
        mock_ta.propagate.return_value = (state, "BUY")

        with (
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}),
            patch("trader.analyzer.TradingAgentsGraph", return_value=mock_ta),
        ):
            result = run_analysis("NVDA", "2026-01-15")

        assert result["market_report"] == "Bullish conditions."
        assert result["fundamentals_report"] == "Strong revenue."
        assert result["trader_plan"] == "Buy on dips."

    def test_investment_debate_extracted(self):
        mock_ta = MagicMock()
        state = _make_final_state(bull_history="Strong bull case.", bear_history="Weak bear case.")
        mock_ta.propagate.return_value = (state, "BUY")

        with (
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}),
            patch("trader.analyzer.TradingAgentsGraph", return_value=mock_ta),
        ):
            result = run_analysis("NVDA", "2026-01-15")

        assert result["investment_debate"]["bull_history"] == "Strong bull case."
        assert result["investment_debate"]["bear_history"] == "Weak bear case."

    def test_risk_debate_extracted(self):
        mock_ta = MagicMock()
        state = _make_final_state(
            aggressive_history="Aggressive view.", risk_judge="Moderate risk."
        )
        mock_ta.propagate.return_value = (state, "BUY")

        with (
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}),
            patch("trader.analyzer.TradingAgentsGraph", return_value=mock_ta),
        ):
            result = run_analysis("NVDA", "2026-01-15")

        assert result["risk_debate"]["aggressive_history"] == "Aggressive view."
        assert result["risk_debate"]["judge_decision"] == "Moderate risk."

    def test_none_fields_become_empty_string(self):
        mock_ta = MagicMock()
        state = _make_final_state(market_report=None, sentiment_report=None)
        mock_ta.propagate.return_value = (state, "BUY")

        with (
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}),
            patch("trader.analyzer.TradingAgentsGraph", return_value=mock_ta),
        ):
            result = run_analysis("NVDA", "2026-01-15")

        assert result["market_report"] == ""
        assert result["sentiment_report"] == ""

    def test_raises_runtime_error_on_pipeline_failure(self):
        mock_ta = MagicMock()
        mock_ta.propagate.side_effect = Exception("API timeout")

        with (
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}),
            patch("trader.analyzer.TradingAgentsGraph", return_value=mock_ta),
        ):
            with pytest.raises(RuntimeError, match="pipeline failed"):
                run_analysis("NVDA", "2026-01-15")

    def test_uses_all_four_analysts(self):
        mock_ta = MagicMock()
        mock_ta.propagate.return_value = (_make_final_state(), "BUY")

        with (
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}),
            patch("trader.analyzer.TradingAgentsGraph", return_value=mock_ta) as mock_cls,
        ):
            run_analysis("NVDA", "2026-01-15")

        call_kwargs = mock_cls.call_args[1]
        analysts = call_kwargs.get("selected_analysts")
        assert set(analysts) == {"market", "social", "news", "fundamentals"}

    def test_config_uses_anthropic_provider(self):
        mock_ta = MagicMock()
        mock_ta.propagate.return_value = (_make_final_state(), "BUY")

        with (
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}),
            patch("trader.analyzer.TradingAgentsGraph", return_value=mock_ta) as mock_cls,
        ):
            run_analysis("NVDA", "2026-01-15")

        call_kwargs = mock_cls.call_args[1]
        config = call_kwargs.get("config")
        assert config.llm_provider == "anthropic"
        assert config.deep_think_llm == "claude-sonnet-4-6"


# ── render_report ─────────────────────────────────────────────────────────────


class TestRenderReport:
    def test_contains_symbol_and_date(self, sample_result):
        report = render_report(sample_result)
        assert "NVDA" in report
        assert "2026-01-15" in report

    def test_contains_decision(self, sample_result):
        report = render_report(sample_result)
        assert "BUY" in report

    def test_contains_all_report_sections(self, sample_result):
        report = render_report(sample_result)
        assert "Market Analysis" in report
        assert "Sentiment Analysis" in report
        assert "News Analysis" in report
        assert "Fundamentals Analysis" in report

    def test_contains_debate_sections(self, sample_result):
        report = render_report(sample_result)
        assert "Investment Debate" in report
        assert "Bull Case" in report
        assert "Bear Case" in report

    def test_contains_risk_sections(self, sample_result):
        report = render_report(sample_result)
        assert "Risk Assessment" in report
        assert "Aggressive View" in report
        assert "Conservative View" in report
        assert "Neutral View" in report

    def test_contains_final_decision(self, sample_result):
        report = render_report(sample_result)
        assert "Final Trade Decision" in report
        assert "strong fundamentals" in report

    def test_empty_sections_omitted(self, sample_result):
        sample_result["market_report"] = ""
        sample_result["sentiment_report"] = ""
        report = render_report(sample_result)
        assert "Market Analysis" not in report
        assert "Sentiment Analysis" not in report

    def test_returns_string(self, sample_result):
        report = render_report(sample_result)
        assert isinstance(report, str)

    def test_contains_analyzed_at(self, sample_result):
        report = render_report(sample_result)
        assert "2026-01-15T10:00:00Z" in report


# ── main (script) ─────────────────────────────────────────────────────────────


class TestMain:
    def test_writes_report_and_prints_path(self, tmp_path, capsys, sample_result):
        with (
            patch.object(analyze_stock, "TMP_DIR", tmp_path),
            patch("trader_analyze_stock.run_analysis", return_value=sample_result),
            patch("trader_analyze_stock.render_report", return_value="# Report"),
            patch("sys.argv", ["analyze_stock.py", "--symbol", "NVDA"]),
        ):
            analyze_stock.main()

        captured = capsys.readouterr()
        output_path = Path(captured.out.strip())
        assert output_path.exists()
        assert output_path.suffix == ".md"
        assert "NVDA" in output_path.name
        assert output_path.read_text(encoding="utf-8") == "# Report"

    def test_symbol_is_uppercased(self, tmp_path, sample_result):
        with (
            patch.object(analyze_stock, "TMP_DIR", tmp_path),
            patch("trader_analyze_stock.run_analysis", return_value=sample_result) as mock_run,
            patch("trader_analyze_stock.render_report", return_value=""),
            patch("sys.argv", ["analyze_stock.py", "--symbol", "nvda"]),
        ):
            analyze_stock.main()

        call_args = mock_run.call_args[0]
        assert call_args[0] == "NVDA"

    def test_date_passed_when_provided(self, tmp_path, sample_result):
        with (
            patch.object(analyze_stock, "TMP_DIR", tmp_path),
            patch("trader_analyze_stock.run_analysis", return_value=sample_result) as mock_run,
            patch("trader_analyze_stock.render_report", return_value=""),
            patch("sys.argv", ["analyze_stock.py", "--symbol", "NVDA", "--date", "2026-03-01"]),
        ):
            analyze_stock.main()

        call_args = mock_run.call_args[0]
        assert call_args[1] == "2026-03-01"

    def test_defaults_date_to_today(self, tmp_path, sample_result):
        with (
            patch.object(analyze_stock, "TMP_DIR", tmp_path),
            patch("trader_analyze_stock.run_analysis", return_value=sample_result) as mock_run,
            patch("trader_analyze_stock.render_report", return_value=""),
            patch("time.strftime", return_value="2026-05-04"),
            patch("sys.argv", ["analyze_stock.py", "--symbol", "NVDA"]),
        ):
            analyze_stock.main()

        call_args = mock_run.call_args[0]
        assert call_args[1] == "2026-05-04"

    def test_exits_on_environment_error(self, tmp_path):
        with (
            patch.object(analyze_stock, "TMP_DIR", tmp_path),
            patch(
                "trader_analyze_stock.run_analysis",
                side_effect=OSError("ANTHROPIC_API_KEY not set"),
            ),
            patch("sys.argv", ["analyze_stock.py", "--symbol", "NVDA"]),
        ):
            with pytest.raises(SystemExit) as exc_info:
                analyze_stock.main()

        assert exc_info.value.code == 1

    def test_exits_on_runtime_error(self, tmp_path):
        with (
            patch.object(analyze_stock, "TMP_DIR", tmp_path),
            patch(
                "trader_analyze_stock.run_analysis",
                side_effect=RuntimeError("pipeline failed"),
            ),
            patch("sys.argv", ["analyze_stock.py", "--symbol", "NVDA"]),
        ):
            with pytest.raises(SystemExit) as exc_info:
                analyze_stock.main()

        assert exc_info.value.code == 1

    def test_exits_on_unexpected_error(self, tmp_path):
        with (
            patch.object(analyze_stock, "TMP_DIR", tmp_path),
            patch(
                "trader_analyze_stock.run_analysis",
                side_effect=ValueError("unexpected"),
            ),
            patch("sys.argv", ["analyze_stock.py", "--symbol", "NVDA"]),
        ):
            with pytest.raises(SystemExit) as exc_info:
                analyze_stock.main()

        assert exc_info.value.code == 1

    def test_no_file_written_on_error(self, tmp_path):
        with (
            patch.object(analyze_stock, "TMP_DIR", tmp_path),
            patch(
                "trader_analyze_stock.run_analysis",
                side_effect=RuntimeError("pipeline failed"),
            ),
            patch("sys.argv", ["analyze_stock.py", "--symbol", "NVDA"]),
        ):
            with pytest.raises(SystemExit):
                analyze_stock.main()

        assert list(tmp_path.iterdir()) == []

    def test_symbol_required(self):
        with patch("sys.argv", ["analyze_stock.py"]):
            with pytest.raises(SystemExit) as exc_info:
                analyze_stock.main()

        assert exc_info.value.code == 2

    def test_creates_tmp_dir_if_missing(self, tmp_path, sample_result):
        nested = tmp_path / "nested" / "tmp"
        with (
            patch.object(analyze_stock, "TMP_DIR", nested),
            patch("trader_analyze_stock.run_analysis", return_value=sample_result),
            patch("trader_analyze_stock.render_report", return_value="# Report"),
            patch("sys.argv", ["analyze_stock.py", "--symbol", "NVDA"]),
        ):
            analyze_stock.main()

        assert nested.exists()
