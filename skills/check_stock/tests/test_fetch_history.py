"""Tests for fetch_history.py and check_stock.fetcher.fetch_history."""

import json
import logging
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import fetch_history
from check_stock.fetcher import fetch_history as fetch_history_fn


@pytest.fixture(autouse=True)
def reset_logger():
    yield
    logging.getLogger("finance_agent").handlers.clear()


def _make_df(rows: list[dict]):
    """Build a minimal DataFrame mirroring yfinance .history() output."""
    import pandas as pd

    if not rows:
        return pd.DataFrame()

    index = pd.to_datetime([r["date"] for r in rows], utc=True)
    data = {
        "Open": [r["open"] for r in rows],
        "High": [r["high"] for r in rows],
        "Low": [r["low"] for r in rows],
        "Close": [r["close"] for r in rows],
        "Volume": [r["volume"] for r in rows],
    }
    return pd.DataFrame(data, index=index)


SAMPLE_ROWS = [
    {
        "date": "2026-01-02",
        "open": 200.0,
        "high": 210.0,
        "low": 198.0,
        "close": 207.5,
        "volume": 30_000_000,
    },
    {
        "date": "2026-01-03",
        "open": 207.5,
        "high": 215.0,
        "low": 205.0,
        "close": 212.0,
        "volume": 28_000_000,
    },
    {
        "date": "2026-01-04",
        "open": 212.0,
        "high": 214.0,
        "low": 208.0,
        "close": 209.0,
        "volume": 25_000_000,
    },
]


# ── fetch_history (library) ───────────────────────────────────────────────────


class TestFetchHistory:
    def test_returns_expected_shape(self):
        df = _make_df(SAMPLE_ROWS)
        with patch("yfinance.Ticker") as mock_ticker:
            mock_ticker.return_value.history.return_value = df
            result = fetch_history_fn("AMZN", "NASDAQ", "1y")

        assert result["symbol"] == "AMZN"
        assert result["market"] == "NASDAQ"
        assert result["period"] == "1y"
        assert "fetched_at" in result
        assert len(result["bars"]) == 3

    def test_bar_fields_present(self):
        df = _make_df(SAMPLE_ROWS)
        with patch("yfinance.Ticker") as mock_ticker:
            mock_ticker.return_value.history.return_value = df
            result = fetch_history_fn("AMZN", None, "1y")

        bar = result["bars"][0]
        assert set(bar.keys()) == {"date", "open", "high", "low", "close", "volume"}

    def test_bar_date_format(self):
        df = _make_df(SAMPLE_ROWS)
        with patch("yfinance.Ticker") as mock_ticker:
            mock_ticker.return_value.history.return_value = df
            result = fetch_history_fn("AMZN", None, "1y")

        for bar in result["bars"]:
            assert len(bar["date"]) == 10
            assert bar["date"][4] == "-" and bar["date"][7] == "-"

    def test_volume_is_int(self):
        df = _make_df(SAMPLE_ROWS)
        with patch("yfinance.Ticker") as mock_ticker:
            mock_ticker.return_value.history.return_value = df
            result = fetch_history_fn("AMZN", None, "1y")

        for bar in result["bars"]:
            assert isinstance(bar["volume"], int)

    def test_raises_on_invalid_period(self):
        with pytest.raises(ValueError, match="Invalid period"):
            fetch_history_fn("AMZN", None, "99y")

    def test_raises_on_empty_dataframe(self):
        import pandas as pd

        with patch("yfinance.Ticker") as mock_ticker:
            mock_ticker.return_value.history.return_value = pd.DataFrame()
            with pytest.raises(ValueError, match="No historical data"):
                fetch_history_fn("AMZN", None, "1y")

    def test_default_period_is_1y(self):
        df = _make_df(SAMPLE_ROWS)
        with patch("yfinance.Ticker") as mock_ticker:
            mock_ticker.return_value.history.return_value = df
            result = fetch_history_fn("AMZN", None)

        assert result["period"] == "1y"
        mock_ticker.return_value.history.assert_called_once_with(period="1y", interval="1d")

    def test_passes_period_to_yfinance(self):
        df = _make_df(SAMPLE_ROWS)
        with patch("yfinance.Ticker") as mock_ticker:
            mock_ticker.return_value.history.return_value = df
            fetch_history_fn("AMZN", None, "6mo")

        mock_ticker.return_value.history.assert_called_once_with(period="6mo", interval="1d")


# ── main (script) ─────────────────────────────────────────────────────────────

SAMPLE_RESULT = {
    "symbol": "AMZN",
    "market": None,
    "period": "1y",
    "fetched_at": "2026-03-16T10:00:00Z",
    "bars": SAMPLE_ROWS,
}


class TestMain:
    def test_writes_json_and_prints_path(self, tmp_path, capsys):
        with (
            patch.object(fetch_history, "TMP_DIR", tmp_path),
            patch("fetch_history.fetch_history_data", return_value=SAMPLE_RESULT),
            patch("sys.argv", ["fetch_history.py", "--symbol", "AMZN"]),
        ):
            fetch_history.main()

        captured = capsys.readouterr()
        output_path = Path(captured.out.strip())
        assert output_path.exists()
        assert "AMZN" in output_path.name
        assert "1y" in output_path.name
        data = json.loads(output_path.read_text())
        assert data == SAMPLE_RESULT

    def test_symbol_uppercased(self, tmp_path):
        with (
            patch.object(fetch_history, "TMP_DIR", tmp_path),
            patch("fetch_history.fetch_history_data", return_value=SAMPLE_RESULT) as mock_fn,
            patch("sys.argv", ["fetch_history.py", "--symbol", "amzn"]),
        ):
            fetch_history.main()

        mock_fn.assert_called_once_with("AMZN", None, "1y")

    def test_default_period(self, tmp_path):
        with (
            patch.object(fetch_history, "TMP_DIR", tmp_path),
            patch("fetch_history.fetch_history_data", return_value=SAMPLE_RESULT) as mock_fn,
            patch("sys.argv", ["fetch_history.py", "--symbol", "AMZN"]),
        ):
            fetch_history.main()

        mock_fn.assert_called_once_with("AMZN", None, "1y")

    def test_custom_period(self, tmp_path):
        with (
            patch.object(fetch_history, "TMP_DIR", tmp_path),
            patch("fetch_history.fetch_history_data", return_value=SAMPLE_RESULT) as mock_fn,
            patch("sys.argv", ["fetch_history.py", "--symbol", "AMZN", "--period", "6mo"]),
        ):
            fetch_history.main()

        mock_fn.assert_called_once_with("AMZN", None, "6mo")

    def test_passes_market(self, tmp_path):
        with (
            patch.object(fetch_history, "TMP_DIR", tmp_path),
            patch("fetch_history.fetch_history_data", return_value=SAMPLE_RESULT) as mock_fn,
            patch("sys.argv", ["fetch_history.py", "--symbol", "AMZN", "--market", "NASDAQ"]),
        ):
            fetch_history.main()

        mock_fn.assert_called_once_with("AMZN", "NASDAQ", "1y")

    def test_exits_on_value_error(self, tmp_path):
        with (
            patch.object(fetch_history, "TMP_DIR", tmp_path),
            patch("fetch_history.fetch_history_data", side_effect=ValueError("bad period")),
            patch("sys.argv", ["fetch_history.py", "--symbol", "AMZN"]),
        ):
            with pytest.raises(SystemExit) as exc_info:
                fetch_history.main()

        assert exc_info.value.code == 1

    def test_exits_on_unexpected_error(self, tmp_path):
        with (
            patch.object(fetch_history, "TMP_DIR", tmp_path),
            patch("fetch_history.fetch_history_data", side_effect=RuntimeError("network error")),
            patch("sys.argv", ["fetch_history.py", "--symbol", "AMZN"]),
        ):
            with pytest.raises(SystemExit) as exc_info:
                fetch_history.main()

        assert exc_info.value.code == 1

    def test_symbol_required(self):
        with patch("sys.argv", ["fetch_history.py"]):
            with pytest.raises(SystemExit) as exc_info:
                fetch_history.main()

        assert exc_info.value.code == 2

    def test_creates_tmp_dir_if_missing(self, tmp_path):
        nested = tmp_path / "nested" / "tmp"
        with (
            patch.object(fetch_history, "TMP_DIR", nested),
            patch("fetch_history.fetch_history_data", return_value=SAMPLE_RESULT),
            patch("sys.argv", ["fetch_history.py", "--symbol", "AMZN"]),
        ):
            fetch_history.main()

        assert nested.exists()
