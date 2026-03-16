"""Tests for fetch_history.py and check_crypto.fetcher.fetch_history."""

import importlib.util
import json
import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_spec = importlib.util.spec_from_file_location(
    "check_crypto_fetch_history", Path(__file__).parent.parent / "scripts" / "fetch_history.py"
)
fetch_history = importlib.util.module_from_spec(_spec)
sys.modules["check_crypto_fetch_history"] = fetch_history
_spec.loader.exec_module(fetch_history)
from check_crypto.fetcher import fetch_history as fetch_history_fn  # noqa: E402


@pytest.fixture(autouse=True)
def reset_logger():
    yield
    logging.getLogger("finance_agent").handlers.clear()


SAMPLE_OHLC = [
    [1736899200000, 94000.0, 96000.0, 93000.0, 95500.0],
    [1736985600000, 95500.0, 97000.0, 94500.0, 96200.0],
    [1737072000000, 96200.0, 98000.0, 95000.0, 97100.0],
]

SAMPLE_RESULT = {
    "coin_id": "bitcoin",
    "days": 365,
    "bars": [
        {"date": "2025-01-15", "open": 94000.0, "high": 96000.0, "low": 93000.0, "close": 95500.0},
        {"date": "2025-01-16", "open": 95500.0, "high": 97000.0, "low": 94500.0, "close": 96200.0},
        {"date": "2025-01-17", "open": 96200.0, "high": 98000.0, "low": 95000.0, "close": 97100.0},
    ],
}


def _patch_cg(ohlc_data):
    mock_cg = MagicMock()
    mock_cg.get_coin_ohlc_by_id.return_value = ohlc_data if ohlc_data else []
    return patch("check_crypto.fetcher.CoinGeckoAPI", return_value=mock_cg)


# ── fetch_history (library) ───────────────────────────────────────────────────


class TestFetchHistory:
    def test_returns_expected_shape(self):
        with _patch_cg(SAMPLE_OHLC):
            result = fetch_history_fn("bitcoin", 365)

        assert result["coin_id"] == "bitcoin"
        assert result["days"] == 365
        assert len(result["bars"]) == 3

    def test_bar_fields_present(self):
        with _patch_cg(SAMPLE_OHLC):
            result = fetch_history_fn("bitcoin", 365)

        bar = result["bars"][0]
        assert set(bar.keys()) == {"date", "open", "high", "low", "close"}

    def test_bar_date_format(self):
        with _patch_cg(SAMPLE_OHLC):
            result = fetch_history_fn("bitcoin", 365)

        for bar in result["bars"]:
            assert len(bar["date"]) == 10
            assert bar["date"][4] == "-" and bar["date"][7] == "-"

    def test_raises_on_empty_response(self):
        with _patch_cg([]):
            with pytest.raises(ValueError, match="no OHLC data"):
                fetch_history_fn("bitcoin", 365)

    def test_raises_on_none_response(self):
        mock_cg = MagicMock()
        mock_cg.get_coin_ohlc_by_id.return_value = None
        with patch("check_crypto.fetcher.CoinGeckoAPI", return_value=mock_cg):
            with pytest.raises(ValueError, match="no OHLC data"):
                fetch_history_fn("bitcoin", 365)

    def test_default_days_is_365(self):
        with _patch_cg(SAMPLE_OHLC):
            result = fetch_history_fn("bitcoin")

        assert result["days"] == 365

    def test_passes_days_to_api(self):
        mock_cg = MagicMock()
        mock_cg.get_coin_ohlc_by_id.return_value = SAMPLE_OHLC
        with patch("check_crypto.fetcher.CoinGeckoAPI", return_value=mock_cg):
            fetch_history_fn("bitcoin", 90)

        mock_cg.get_coin_ohlc_by_id.assert_called_once_with("bitcoin", vs_currency="usd", days="90")


# ── main (script) ─────────────────────────────────────────────────────────────


class TestMain:
    def test_writes_json_and_prints_path(self, tmp_path, capsys):
        with (
            patch.object(fetch_history, "TMP_DIR", tmp_path),
            patch("check_crypto_fetch_history.fetch_history_data", return_value=SAMPLE_RESULT),
            patch("sys.argv", ["fetch_history.py", "--coin", "bitcoin"]),
        ):
            fetch_history.main()

        captured = capsys.readouterr()
        output_path = Path(captured.out.strip())
        assert output_path.exists()
        assert "bitcoin" in output_path.name
        assert "365d" in output_path.name
        data = json.loads(output_path.read_text())
        assert data == SAMPLE_RESULT

    def test_coin_lowercased(self, tmp_path):
        with (
            patch.object(fetch_history, "TMP_DIR", tmp_path),
            patch("check_crypto_fetch_history.fetch_history_data", return_value=SAMPLE_RESULT) as mock_fn,
            patch("sys.argv", ["fetch_history.py", "--coin", "Bitcoin"]),
        ):
            fetch_history.main()

        mock_fn.assert_called_once_with("bitcoin", 365)

    def test_default_days(self, tmp_path):
        with (
            patch.object(fetch_history, "TMP_DIR", tmp_path),
            patch("check_crypto_fetch_history.fetch_history_data", return_value=SAMPLE_RESULT) as mock_fn,
            patch("sys.argv", ["fetch_history.py", "--coin", "bitcoin"]),
        ):
            fetch_history.main()

        mock_fn.assert_called_once_with("bitcoin", 365)

    def test_custom_days(self, tmp_path):
        with (
            patch.object(fetch_history, "TMP_DIR", tmp_path),
            patch("check_crypto_fetch_history.fetch_history_data", return_value=SAMPLE_RESULT) as mock_fn,
            patch("sys.argv", ["fetch_history.py", "--coin", "bitcoin", "--days", "90"]),
        ):
            fetch_history.main()

        mock_fn.assert_called_once_with("bitcoin", 90)

    def test_exits_on_value_error(self, tmp_path):
        with (
            patch.object(fetch_history, "TMP_DIR", tmp_path),
            patch("check_crypto_fetch_history.fetch_history_data", side_effect=ValueError("not found")),
            patch("sys.argv", ["fetch_history.py", "--coin", "bitcoin"]),
        ):
            with pytest.raises(SystemExit) as exc_info:
                fetch_history.main()

        assert exc_info.value.code == 1

    def test_exits_on_unexpected_error(self, tmp_path):
        with (
            patch.object(fetch_history, "TMP_DIR", tmp_path),
            patch("check_crypto_fetch_history.fetch_history_data", side_effect=RuntimeError("network error")),
            patch("sys.argv", ["fetch_history.py", "--coin", "bitcoin"]),
        ):
            with pytest.raises(SystemExit) as exc_info:
                fetch_history.main()

        assert exc_info.value.code == 1

    def test_coin_required(self):
        with patch("sys.argv", ["fetch_history.py"]):
            with pytest.raises(SystemExit) as exc_info:
                fetch_history.main()

        assert exc_info.value.code == 2

    def test_creates_tmp_dir_if_missing(self, tmp_path):
        nested = tmp_path / "nested" / "tmp"
        with (
            patch.object(fetch_history, "TMP_DIR", nested),
            patch("check_crypto_fetch_history.fetch_history_data", return_value=SAMPLE_RESULT),
            patch("sys.argv", ["fetch_history.py", "--coin", "bitcoin"]),
        ):
            fetch_history.main()

        assert nested.exists()
