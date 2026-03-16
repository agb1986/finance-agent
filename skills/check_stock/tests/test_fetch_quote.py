"""Tests for fetch_quote.py and check_stock.fetcher.fetch_quote."""

import importlib.util
import json
import logging
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_spec = importlib.util.spec_from_file_location(
    "check_stock_fetch_quote", Path(__file__).parent.parent / "scripts" / "fetch_quote.py"
)
fetch_quote = importlib.util.module_from_spec(_spec)
sys.modules["check_stock_fetch_quote"] = fetch_quote
_spec.loader.exec_module(fetch_quote)
from check_stock.fetcher import fetch_quote as fetch_quote_fn  # noqa: E402


@pytest.fixture(autouse=True)
def reset_logger():
    yield
    logging.getLogger("finance_agent").handlers.clear()


SAMPLE_QUOTE = {
    "symbol": "AMZN",
    "market": "NASDAQ",
    "fetched_at": "2026-03-16T09:00:00Z",
    "name": "Amazon.com, Inc.",
    "price": 185.50,
    "currency": "USD",
    "change": 2.30,
    "change_percent": 1.25,
    "volume": 32_000_000,
    "market_cap": 1_950_000_000_000,
    "pe_ratio": 38.2,
    "week_52_high": 230.00,
    "week_52_low": 151.61,
}


# ── fetch_quote (library) ─────────────────────────────────────────────────────


def _make_info(**kwargs):
    defaults = {
        "currentPrice": 207.67,
        "previousClose": 209.53,
        "currency": "USD",
        "longName": "Amazon.com, Inc.",
        "regularMarketVolume": 35_000_000,
        "marketCap": 2_200_000_000_000,
        "trailingPE": 29.0,
        "fiftyTwoWeekHigh": 258.6,
        "fiftyTwoWeekLow": 161.38,
    }
    defaults.update(kwargs)
    return defaults


class TestFetchQuote:
    def test_returns_expected_fields(self):
        with patch("yfinance.Ticker") as mock_ticker:
            mock_ticker.return_value.info = _make_info()
            result = fetch_quote_fn("AMZN", "NASDAQ")

        assert result["symbol"] == "AMZN"
        assert result["market"] == "NASDAQ"
        assert "fetched_at" in result
        assert set(result.keys()) == {
            "symbol",
            "market",
            "fetched_at",
            "name",
            "price",
            "currency",
            "change",
            "change_percent",
            "volume",
            "market_cap",
            "pe_ratio",
            "week_52_high",
            "week_52_low",
        }

    def test_computes_change_from_previous_close(self):
        with patch("yfinance.Ticker") as mock_ticker:
            mock_ticker.return_value.info = _make_info(currentPrice=210.0, previousClose=200.0)
            result = fetch_quote_fn("AMZN", None)

        assert result["change"] == pytest.approx(10.0, abs=0.01)
        assert result["change_percent"] == pytest.approx(5.0, abs=0.01)

    def test_change_is_none_when_price_missing(self):
        with patch("yfinance.Ticker") as mock_ticker:
            mock_ticker.return_value.info = _make_info(currentPrice=None, regularMarketPrice=None)
            result = fetch_quote_fn("AMZN", None)

        assert result["change"] is None
        assert result["change_percent"] is None

    def test_falls_back_to_regular_market_price(self):
        with patch("yfinance.Ticker") as mock_ticker:
            mock_ticker.return_value.info = _make_info(currentPrice=None, regularMarketPrice=195.0)
            result = fetch_quote_fn("AMZN", None)

        assert result["price"] == pytest.approx(195.0)

    def test_uses_long_name(self):
        with patch("yfinance.Ticker") as mock_ticker:
            mock_ticker.return_value.info = _make_info(
                longName="Amazon.com, Inc.", shortName="Amazon"
            )
            result = fetch_quote_fn("AMZN", None)

        assert result["name"] == "Amazon.com, Inc."

    def test_falls_back_to_short_name(self):
        with patch("yfinance.Ticker") as mock_ticker:
            mock_ticker.return_value.info = _make_info(longName=None, shortName="Amazon")
            result = fetch_quote_fn("AMZN", None)

        assert result["name"] == "Amazon"

    def test_none_fields_when_info_missing(self):
        with patch("yfinance.Ticker") as mock_ticker:
            mock_ticker.return_value.info = {}
            result = fetch_quote_fn("AMZN", None)

        assert result["price"] is None
        assert result["pe_ratio"] is None
        assert result["market_cap"] is None
        assert result["week_52_high"] is None
        assert result["week_52_low"] is None

    def test_volume_is_int(self):
        with patch("yfinance.Ticker") as mock_ticker:
            mock_ticker.return_value.info = _make_info()
            result = fetch_quote_fn("AMZN", None)

        assert isinstance(result["volume"], int)

    def test_market_cap_is_int(self):
        with patch("yfinance.Ticker") as mock_ticker:
            mock_ticker.return_value.info = _make_info()
            result = fetch_quote_fn("AMZN", None)

        assert isinstance(result["market_cap"], int)


# ── main (script) ─────────────────────────────────────────────────────────────


class TestMain:
    def test_writes_json_and_prints_path(self, tmp_path, capsys):
        with (
            patch.object(fetch_quote, "TMP_DIR", tmp_path),
            patch("check_stock_fetch_quote.fetch_quote_data", return_value=SAMPLE_QUOTE),
        ):
            with patch("sys.argv", ["fetch_quote.py", "--symbol", "AMZN"]):
                fetch_quote.main()

        captured = capsys.readouterr()
        output_path = Path(captured.out.strip())
        assert output_path.exists()
        assert output_path.suffix == ".json"
        assert "AMZN" in output_path.name

        data = json.loads(output_path.read_text())
        assert data == SAMPLE_QUOTE

    def test_passes_market_to_fetcher(self, tmp_path):
        with (
            patch.object(fetch_quote, "TMP_DIR", tmp_path),
            patch("check_stock_fetch_quote.fetch_quote_data", return_value=SAMPLE_QUOTE) as mock_fetch,
        ):
            with patch("sys.argv", ["fetch_quote.py", "--symbol", "AMZN", "--market", "NASDAQ"]):
                fetch_quote.main()

        mock_fetch.assert_called_once_with("AMZN", "NASDAQ")

    def test_symbol_uppercased(self, tmp_path):
        with (
            patch.object(fetch_quote, "TMP_DIR", tmp_path),
            patch("check_stock_fetch_quote.fetch_quote_data", return_value=SAMPLE_QUOTE) as mock_fetch,
        ):
            with patch("sys.argv", ["fetch_quote.py", "--symbol", "amzn"]):
                fetch_quote.main()

        mock_fetch.assert_called_once_with("AMZN", None)

    def test_exits_on_not_implemented(self, tmp_path):
        with (
            patch.object(fetch_quote, "TMP_DIR", tmp_path),
            patch("check_stock_fetch_quote.fetch_quote_data", side_effect=NotImplementedError("stub")),
        ):
            with patch("sys.argv", ["fetch_quote.py", "--symbol", "AMZN"]):
                with pytest.raises(SystemExit) as exc_info:
                    fetch_quote.main()

        assert exc_info.value.code == 1

    def test_exits_on_fetch_error(self, tmp_path):
        with (
            patch.object(fetch_quote, "TMP_DIR", tmp_path),
            patch("check_stock_fetch_quote.fetch_quote_data", side_effect=RuntimeError("API error")),
        ):
            with patch("sys.argv", ["fetch_quote.py", "--symbol", "AMZN"]):
                with pytest.raises(SystemExit) as exc_info:
                    fetch_quote.main()

        assert exc_info.value.code == 1

    def test_symbol_required(self):
        with patch("sys.argv", ["fetch_quote.py"]):
            with pytest.raises(SystemExit) as exc_info:
                fetch_quote.main()

        assert exc_info.value.code == 2

    def test_no_file_written_on_error(self, tmp_path):
        with (
            patch.object(fetch_quote, "TMP_DIR", tmp_path),
            patch("check_stock_fetch_quote.fetch_quote_data", side_effect=RuntimeError("API error")),
        ):
            with patch("sys.argv", ["fetch_quote.py", "--symbol", "AMZN"]):
                with pytest.raises(SystemExit):
                    fetch_quote.main()

        assert list(tmp_path.iterdir()) == []

    def test_creates_tmp_dir_if_missing(self, tmp_path):
        nested = tmp_path / "nested" / "tmp"
        with (
            patch.object(fetch_quote, "TMP_DIR", nested),
            patch("check_stock_fetch_quote.fetch_quote_data", return_value=SAMPLE_QUOTE),
        ):
            with patch("sys.argv", ["fetch_quote.py", "--symbol", "AMZN"]):
                fetch_quote.main()

        assert nested.exists()
