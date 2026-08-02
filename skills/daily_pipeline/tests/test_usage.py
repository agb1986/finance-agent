"""Tests for daily_pipeline.usage (cost estimation and Markdown rendering)."""

import json
import logging
from pathlib import Path

import pytest
from daily_pipeline.usage import (
    estimate_cost,
    format_money,
    format_usage_section,
    split_verdict_usage,
)


@pytest.fixture(autouse=True)
def reset_logger():
    yield
    logging.getLogger("finance_agent").handlers.clear()


def _counts(input_tokens=0, output_tokens=0, cache_read=0, cache_write=0, calls=1) -> dict:
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_input_tokens": cache_read,
        "cache_creation_input_tokens": cache_write,
        "calls": calls,
    }


RATES = {
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "claude-opus-4-8": {"input": 5.00, "output": 25.00},
}
PRICING = {"currency": "$", "models": RATES}


class TestEstimateCost:
    def test_prices_input_and_output_per_million(self):
        totals = {"claude-opus-4-8": _counts(input_tokens=1_000_000, output_tokens=1_000_000)}
        cost, unpriced = estimate_cost(totals, RATES)
        assert cost == pytest.approx(30.00)
        assert unpriced == []

    def test_sums_across_models(self):
        totals = {
            "claude-sonnet-4-6": _counts(input_tokens=1_000_000),
            "claude-opus-4-8": _counts(input_tokens=1_000_000),
        }
        cost, _ = estimate_cost(totals, RATES)
        assert cost == pytest.approx(8.00)

    def test_cache_reads_are_discounted(self):
        totals = {"claude-opus-4-8": _counts(cache_read=1_000_000)}
        cost, _ = estimate_cost(totals, RATES)
        assert cost == pytest.approx(0.50)  # 0.1x the $5 input rate

    def test_cache_writes_carry_a_premium(self):
        totals = {"claude-opus-4-8": _counts(cache_write=1_000_000)}
        cost, _ = estimate_cost(totals, RATES)
        assert cost == pytest.approx(6.25)  # 1.25x the $5 input rate

    def test_unpriced_model_is_named_not_silently_zero(self):
        totals = {"some-new-model": _counts(input_tokens=1_000_000)}
        cost, unpriced = estimate_cost(totals, RATES)
        assert cost == 0.0
        assert unpriced == ["some-new-model"]

    def test_empty_inputs(self):
        assert estimate_cost(None, None) == (0.0, [])


class TestFormatMoney:
    def test_two_decimals_normally(self):
        assert format_money(1.5) == "$1.50"

    def test_sub_cent_does_not_round_to_zero(self):
        assert format_money(0.0034) == "$0.0034"

    def test_zero_uses_two_decimals(self):
        assert format_money(0.0) == "$0.00"

    def test_respects_currency(self):
        assert format_money(2.0, "£") == "£2.00"

    def test_thousands_separator(self):
        assert format_money(1234.5) == "$1,234.50"


class TestFormatUsageSection:
    def test_no_calls_at_all(self):
        assert "No Anthropic API calls" in format_usage_section({}, {}, PRICING)

    def test_renders_row_per_model_and_a_total(self):
        spent = {
            "claude-sonnet-4-6": _counts(input_tokens=1_000_000, output_tokens=0, calls=5),
            "claude-opus-4-8": _counts(input_tokens=1_000_000, output_tokens=0, calls=5),
        }
        section = format_usage_section(spent, {}, PRICING)
        assert "| claude-sonnet-4-6 | 5 | 1,000,000 | 0 | $3.00 |" in section
        assert "| claude-opus-4-8 | 5 | 1,000,000 | 0 | $5.00 |" in section
        assert "| **Total** | **10** | **2,000,000** | **0** | **$8.00** |" in section

    def test_flags_unpriced_models_below_the_table(self):
        spent = {"mystery-model": _counts(input_tokens=100, calls=1)}
        section = format_usage_section(spent, {}, PRICING)
        assert "No configured price for mystery-model" in section
        assert "| mystery-model | 1 | 100 | 0 | — |" in section

    def test_cached_usage_reported_separately_from_todays_spend(self):
        spent = {"claude-opus-4-8": _counts(input_tokens=1_000_000, calls=1)}
        reused = {"claude-opus-4-8": _counts(input_tokens=2_000_000, calls=10)}
        section = format_usage_section(spent, reused, PRICING)
        # Today's total must not absorb the cached tokens.
        assert "**1,000,000**" in section
        assert "Reused 10 cached API calls" in section
        assert "not today" in section

    def test_all_cached_says_nothing_was_charged(self):
        reused = {"claude-opus-4-8": _counts(input_tokens=500, calls=1)}
        section = format_usage_section({}, reused, PRICING)
        assert "every verdict came from cache" in section
        assert "Reused 1 cached API call" in section

    def test_missing_pricing_still_reports_tokens(self):
        spent = {"claude-opus-4-8": _counts(input_tokens=42, calls=1)}
        section = format_usage_section(spent, {}, None)
        assert "42" in section


class TestSplitVerdictUsage:
    def _write(self, tmp_path: Path, name: str, payload: dict) -> str:
        path = tmp_path / name
        path.write_text(json.dumps(payload))
        return str(path)

    def _load(self, path):
        return json.loads(Path(path).read_text())

    def test_separates_cached_from_charged(self, tmp_path):
        fresh = self._write(
            tmp_path, "a.json", {"usage": {"claude-opus-4-8": _counts(input_tokens=10)}}
        )
        cached = self._write(
            tmp_path, "b.json", {"usage": {"claude-opus-4-8": _counts(input_tokens=99)}}
        )
        spent, reused = split_verdict_usage(
            [{"path": fresh, "cached": False}, {"path": cached, "cached": True}], self._load
        )
        assert spent["claude-opus-4-8"]["input_tokens"] == 10
        assert reused["claude-opus-4-8"]["input_tokens"] == 99

    def test_merges_multiple_fresh_verdicts(self, tmp_path):
        entries = [
            {
                "path": self._write(
                    tmp_path, f"{i}.json", {"usage": {"m": _counts(input_tokens=5)}}
                ),
                "cached": False,
            }
            for i in range(3)
        ]
        spent, _ = split_verdict_usage(entries, self._load)
        assert spent["m"]["input_tokens"] == 15
        assert spent["m"]["calls"] == 3

    def test_verdict_without_usage_is_skipped(self, tmp_path):
        # Verdicts written before usage tracking existed have no usage key.
        legacy = self._write(tmp_path, "old.json", {"symbol": "AMZN"})
        assert split_verdict_usage([{"path": legacy, "cached": False}], self._load) == ({}, {})

    def test_unreadable_verdict_is_skipped(self, tmp_path):
        def _boom(_path):
            raise OSError("gone")

        assert split_verdict_usage([{"path": "x", "cached": False}], _boom) == ({}, {})

    def test_no_verdicts(self):
        assert split_verdict_usage([], self._load) == ({}, {})
