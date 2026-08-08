"""Tests for daily_pipeline.context — the trader market-data context builder."""

import logging

import pytest
from daily_pipeline.context import build_context, sma


@pytest.fixture(autouse=True)
def reset_logger():
    yield
    logging.getLogger("finance_agent").handlers.clear()


def _quote(**overrides) -> dict:
    quote = {
        "symbol": "AMZN",
        "fetched_at": "2026-08-08T07:00:00Z",
        "name": "Amazon.com, Inc.",
        "price": 185.5,
        "currency": "USD",
        "change": 1.2,
        "change_percent": 0.65,
        "volume": 12_345_678,
        "market_cap": 1_900_000_000_000,
        "pe_ratio": 40.5,
        "week_52_high": 200.0,
        "week_52_low": 140.0,
    }
    quote.update(overrides)
    return quote


def _history(n_bars: int = 30) -> dict:
    return {
        "symbol": "AMZN",
        "period": "6mo",
        "fetched_at": "2026-08-08T07:00:00Z",
        "bars": [
            {
                "date": f"2026-06-{(i % 28) + 1:02d}",
                "open": 100.0 + i,
                "high": 101.0 + i,
                "low": 99.0 + i,
                "close": 100.5 + i,
                "volume": 1000 + i,
            }
            for i in range(n_bars)
        ],
    }


class TestSma:
    def test_average_of_last_window(self):
        assert sma([1.0, 2.0, 3.0, 4.0], 2) == 3.5

    def test_none_when_too_few_closes(self):
        assert sma([1.0, 2.0], 5) is None

    def test_exact_window(self):
        assert sma([2.0, 4.0], 2) == 3.0


class TestBuildContext:
    def test_contains_quote_fields(self):
        text = build_context(_quote(), _history())
        assert "# AMZN market data" in text
        assert "Amazon.com, Inc." in text
        assert "185.50 USD" in text
        assert "P/E ratio: 40.50" in text
        assert "52-week range: 140.00 – 200.00" in text

    def test_contains_history_summary(self):
        text = build_context(_quote(), _history(30))
        assert "## Price history (6mo, daily, 30 bars)" in text
        assert "SMA20:" in text
        assert "Period range:" in text

    def test_sma_na_when_insufficient_bars(self):
        text = build_context(_quote(), _history(10))
        assert "SMA20: n/a" in text
        assert "SMA200: n/a" in text

    def test_recent_bars_capped_at_ten(self):
        text = build_context(_quote(), _history(30))
        assert "Last 10 bars (oldest first):" in text
        # 10 bar rows plus the header row use the pipe separator
        bar_rows = [line for line in text.splitlines() if line.count(" | ") == 5]
        assert len(bar_rows) == 11

    def test_missing_quote_fields_render_na(self):
        quote = _quote(price=None, pe_ratio=None, name=None)
        text = build_context(quote, _history())
        assert "Price: n/a" in text
        assert "P/E ratio: n/a" in text
        assert "Name: n/a" in text

    def test_empty_history_handled(self):
        text = build_context(_quote(), {"period": "6mo", "bars": []})
        assert "No history bars available." in text

    def test_stays_compact(self):
        # The whole point: the context must stay small enough to send to five
        # panel roles without materially increasing prompt spend.
        text = build_context(_quote(), _history(180))
        assert len(text) < 2500
