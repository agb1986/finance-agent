"""Tests for fetch_quote.py and check_crypto.fetcher.fetch_quote."""

import importlib.util
import json
import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_spec = importlib.util.spec_from_file_location(
    "check_crypto_fetch_quote", Path(__file__).parent.parent / "scripts" / "fetch_quote.py"
)
fetch_quote = importlib.util.module_from_spec(_spec)
sys.modules["check_crypto_fetch_quote"] = fetch_quote
_spec.loader.exec_module(fetch_quote)
from check_crypto.fetcher import fetch_quote as fetch_quote_fn  # noqa: E402


@pytest.fixture(autouse=True)
def reset_logger():
    yield
    logging.getLogger("finance_agent").handlers.clear()


SAMPLE_QUOTE = {
    "coin_id": "bitcoin",
    "symbol": "BTC",
    "name": "Bitcoin",
    "price": 65000.0,
    "currency": "USD",
    "market_cap": 1_280_000_000_000,
    "volume_24h": 35_000_000_000,
    "change_24h": 1200.0,
    "change_percent_24h": 1.88,
    "ath": 73_750.0,
    "atl": 67.81,
    "circulating_supply": 19_680_000.0,
    "total_supply": 21_000_000.0,
    "fetched_at": "2026-03-16T09:00:00Z",
}


def _make_cg_response(**kwargs):
    defaults = {
        "id": "bitcoin",
        "symbol": "btc",
        "name": "Bitcoin",
        "last_updated": "2026-03-16T09:00:00Z",
        "market_data": {
            "current_price": {"usd": 65000.0},
            "market_cap": {"usd": 1_280_000_000_000},
            "total_volume": {"usd": 35_000_000_000},
            "price_change_24h": 1200.0,
            "price_change_percentage_24h": 1.88,
            "ath": {"usd": 73_750.0},
            "atl": {"usd": 67.81},
            "circulating_supply": 19_680_000.0,
            "total_supply": 21_000_000.0,
        },
    }
    defaults.update(kwargs)
    return defaults


# ── fetch_quote (library) ─────────────────────────────────────────────────────


class TestFetchQuote:
    def _patch_cg(self, response):
        mock_cg = MagicMock()
        mock_cg.get_coin_by_id.return_value = response
        return patch("check_crypto.fetcher.CoinGeckoAPI", return_value=mock_cg)

    def test_returns_expected_fields(self):
        with self._patch_cg(_make_cg_response()):
            result = fetch_quote_fn("bitcoin")

        assert result["coin_id"] == "bitcoin"
        assert result["symbol"] == "BTC"
        assert result["name"] == "Bitcoin"
        assert result["currency"] == "USD"
        assert set(result.keys()) == {
            "coin_id",
            "symbol",
            "name",
            "price",
            "currency",
            "market_cap",
            "volume_24h",
            "change_24h",
            "change_percent_24h",
            "ath",
            "atl",
            "circulating_supply",
            "total_supply",
            "fetched_at",
        }

    def test_price_extracted_correctly(self):
        with self._patch_cg(_make_cg_response()):
            result = fetch_quote_fn("bitcoin")

        assert result["price"] == pytest.approx(65000.0)

    def test_symbol_uppercased(self):
        with self._patch_cg(_make_cg_response()):
            result = fetch_quote_fn("bitcoin")

        assert result["symbol"] == "BTC"

    def test_raises_on_empty_response(self):
        mock_cg = MagicMock()
        mock_cg.get_coin_by_id.return_value = None
        with patch("check_crypto.fetcher.CoinGeckoAPI", return_value=mock_cg):
            with pytest.raises(ValueError, match="no data returned"):
                fetch_quote_fn("bitcoin")

    def test_missing_market_data_returns_none_fields(self):
        response = _make_cg_response()
        response["market_data"] = {}
        with self._patch_cg(response):
            result = fetch_quote_fn("bitcoin")

        assert result["price"] is None
        assert result["market_cap"] is None
        assert result["ath"] is None


# ── main (script) ─────────────────────────────────────────────────────────────


class TestMain:
    def test_writes_json_and_prints_path(self, tmp_path, capsys):
        with (
            patch.object(fetch_quote, "TMP_DIR", tmp_path),
            patch("check_crypto_fetch_quote.fetch_quote_data", return_value=SAMPLE_QUOTE),
        ):
            with patch("sys.argv", ["fetch_quote.py", "--coin", "bitcoin"]):
                fetch_quote.main()

        captured = capsys.readouterr()
        output_path = Path(captured.out.strip())
        assert output_path.exists()
        assert output_path.suffix == ".json"
        assert "bitcoin" in output_path.name

        data = json.loads(output_path.read_text())
        assert data == SAMPLE_QUOTE

    def test_coin_lowercased(self, tmp_path):
        with (
            patch.object(fetch_quote, "TMP_DIR", tmp_path),
            patch(
                "check_crypto_fetch_quote.fetch_quote_data", return_value=SAMPLE_QUOTE
            ) as mock_fetch,
        ):
            with patch("sys.argv", ["fetch_quote.py", "--coin", "Bitcoin"]):
                fetch_quote.main()

        mock_fetch.assert_called_once_with("bitcoin")

    def test_exits_on_value_error(self, tmp_path):
        with (
            patch.object(fetch_quote, "TMP_DIR", tmp_path),
            patch("check_crypto_fetch_quote.fetch_quote_data", side_effect=ValueError("not found")),
        ):
            with patch("sys.argv", ["fetch_quote.py", "--coin", "bitcoin"]):
                with pytest.raises(SystemExit) as exc_info:
                    fetch_quote.main()

        assert exc_info.value.code == 1

    def test_exits_on_generic_error(self, tmp_path):
        with (
            patch.object(fetch_quote, "TMP_DIR", tmp_path),
            patch(
                "check_crypto_fetch_quote.fetch_quote_data", side_effect=RuntimeError("API error")
            ),
        ):
            with patch("sys.argv", ["fetch_quote.py", "--coin", "bitcoin"]):
                with pytest.raises(SystemExit) as exc_info:
                    fetch_quote.main()

        assert exc_info.value.code == 1

    def test_coin_required(self):
        with patch("sys.argv", ["fetch_quote.py"]):
            with pytest.raises(SystemExit) as exc_info:
                fetch_quote.main()

        assert exc_info.value.code == 2

    def test_no_file_written_on_error(self, tmp_path):
        with (
            patch.object(fetch_quote, "TMP_DIR", tmp_path),
            patch(
                "check_crypto_fetch_quote.fetch_quote_data", side_effect=RuntimeError("API error")
            ),
        ):
            with patch("sys.argv", ["fetch_quote.py", "--coin", "bitcoin"]):
                with pytest.raises(SystemExit):
                    fetch_quote.main()

        assert list(tmp_path.iterdir()) == []

    def test_creates_tmp_dir_if_missing(self, tmp_path):
        nested = tmp_path / "nested" / "tmp"
        with (
            patch.object(fetch_quote, "TMP_DIR", nested),
            patch("check_crypto_fetch_quote.fetch_quote_data", return_value=SAMPLE_QUOTE),
        ):
            with patch("sys.argv", ["fetch_quote.py", "--coin", "bitcoin"]):
                fetch_quote.main()

        assert nested.exists()
