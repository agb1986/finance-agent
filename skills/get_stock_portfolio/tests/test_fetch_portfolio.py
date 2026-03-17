"""Tests for fetch_portfolio.py, client.py, and formatter.py."""

import base64
import importlib.util
import json
import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests
from get_stock_portfolio.client import fetch_account_summary, fetch_positions, make_client
from get_stock_portfolio.formatter import format_portfolio

_spec = importlib.util.spec_from_file_location(
    "get_stock_portfolio_fetch_portfolio",
    Path(__file__).parent.parent / "scripts" / "fetch_portfolio.py",
)
fetch_portfolio = importlib.util.module_from_spec(_spec)
sys.modules["get_stock_portfolio_fetch_portfolio"] = fetch_portfolio
_spec.loader.exec_module(fetch_portfolio)


@pytest.fixture(autouse=True)
def reset_logger():
    yield
    logging.getLogger("finance_agent").handlers.clear()


SAMPLE_SUMMARY = {
    "id": 12345,
    "currency": "GBP",
    "totalValue": 5500.00,
    "cash": {
        "availableToTrade": 500.00,
        "reservedForOrders": 0,
        "inPies": 0,
    },
    "investments": {
        "currentValue": 5200.00,
        "totalCost": 5000.00,
        "realizedProfitLoss": 50.00,
        "unrealizedProfitLoss": 200.00,
    },
}

SAMPLE_POSITIONS = [
    {
        "instrument": {
            "ticker": "AAPL_US_EQ",
            "name": "Apple",
            "isin": "US0378331005",
            "currency": "USD",
        },
        "createdAt": "2024-01-15T10:30:00+00:00",
        "quantity": 10.0,
        "quantityAvailableForTrading": 10.0,
        "quantityInPies": 0,
        "currentPrice": 170.00,
        "averagePricePaid": 150.00,
        "walletImpact": {
            "currency": "GBP",
            "totalCost": 1500.00,
            "currentValue": 1700.00,
            "unrealizedProfitLoss": 200.00,
            "fxImpact": 0.00,
        },
    },
    {
        "instrument": {
            "ticker": "TSLA_US_EQ",
            "name": "Tesla",
            "isin": "US88160R1014",
            "currency": "USD",
        },
        "createdAt": "2024-02-01T09:00:00+00:00",
        "quantity": 5.0,
        "quantityAvailableForTrading": 5.0,
        "quantityInPies": 0,
        "currentPrice": 180.00,
        "averagePricePaid": 200.00,
        "walletImpact": {
            "currency": "GBP",
            "totalCost": 1000.00,
            "currentValue": 900.00,
            "unrealizedProfitLoss": -100.00,
            "fxImpact": 0.00,
        },
    },
]


# ── client ────────────────────────────────────────────────────────────────────


class TestMakeClient:
    def test_sets_authorization_header(self):
        client = make_client("my-api-key", "my-secret")
        expected = "Basic " + base64.b64encode(b"my-api-key:my-secret").decode()
        assert client.session.headers["Authorization"] == expected

    def test_base_url_is_trading212(self):
        client = make_client("key", "secret")
        assert "trading212.com" in client.base_url


class TestFetchAccountSummary:
    def test_calls_correct_endpoint(self):
        mock_client = MagicMock()
        mock_client.get.return_value = SAMPLE_SUMMARY
        result = fetch_account_summary(mock_client)
        mock_client.get.assert_called_once_with("/api/v0/equity/account/summary")
        assert result == SAMPLE_SUMMARY


class TestFetchPositions:
    def test_calls_correct_endpoint(self):
        mock_client = MagicMock()
        mock_client.get.return_value = SAMPLE_POSITIONS
        result = fetch_positions(mock_client)
        mock_client.get.assert_called_once_with("/api/v0/equity/positions")
        assert result == SAMPLE_POSITIONS


# ── formatter ─────────────────────────────────────────────────────────────────


class TestFormatPortfolio:
    def test_includes_date_in_header(self):
        output = format_portfolio(SAMPLE_SUMMARY, SAMPLE_POSITIONS, "2026-03-17T10:00:00Z")
        assert "2026-03-17" in output

    def test_includes_total_value(self):
        output = format_portfolio(SAMPLE_SUMMARY, SAMPLE_POSITIONS, "2026-03-17T10:00:00Z")
        assert "5,500.00" in output

    def test_includes_invested(self):
        output = format_portfolio(SAMPLE_SUMMARY, SAMPLE_POSITIONS, "2026-03-17T10:00:00Z")
        assert "5,000.00" in output

    def test_unrealised_ppl_positive_has_plus_sign(self):
        output = format_portfolio(SAMPLE_SUMMARY, SAMPLE_POSITIONS, "2026-03-17T10:00:00Z")
        assert "+200.00" in output

    def test_unrealised_ppl_negative_no_plus_sign(self):
        summary = {
            "totalValue": 950.0,
            "investments": {
                "totalCost": 1000.0,
                "unrealizedProfitLoss": -50.0,
                "realizedProfitLoss": 0.0,
            },
        }
        output = format_portfolio(summary, [], "2026-03-17T10:00:00Z")
        assert "-50.00" in output
        assert "+-50.00" not in output

    def test_includes_position_names(self):
        output = format_portfolio(SAMPLE_SUMMARY, SAMPLE_POSITIONS, "2026-03-17T10:00:00Z")
        assert "Apple" in output
        assert "Tesla" in output

    def test_includes_position_isins(self):
        output = format_portfolio(SAMPLE_SUMMARY, SAMPLE_POSITIONS, "2026-03-17T10:00:00Z")
        assert "US0378331005" in output
        assert "US88160R1014" in output

    def test_includes_date_bought_formatted(self):
        output = format_portfolio(SAMPLE_SUMMARY, SAMPLE_POSITIONS, "2026-03-17T10:00:00Z")
        assert "15/01/2024" in output
        assert "01/02/2024" in output

    def test_position_count_shown(self):
        output = format_portfolio(SAMPLE_SUMMARY, SAMPLE_POSITIONS, "2026-03-17T10:00:00Z")
        assert "Open Positions (2)" in output

    def test_no_positions_message(self):
        output = format_portfolio(SAMPLE_SUMMARY, [], "2026-03-17T10:00:00Z")
        assert "No open positions" in output

    def test_positions_sorted_by_value_descending(self):
        output = format_portfolio(SAMPLE_SUMMARY, SAMPLE_POSITIONS, "2026-03-17T10:00:00Z")
        apple_idx = output.index("Apple")
        tesla_idx = output.index("Tesla")
        assert apple_idx < tesla_idx  # Apple currentValue=1700 > Tesla currentValue=900

    def test_position_pnl_calculated_from_cost_and_value(self):
        # Apple: currentValue(1700) - totalCost(1500) = +200
        output = format_portfolio(SAMPLE_SUMMARY, SAMPLE_POSITIONS, "2026-03-17T10:00:00Z")
        assert "+200.00" in output

    def test_position_pnl_negative(self):
        # Tesla: currentValue(900) - totalCost(1000) = -100
        output = format_portfolio(SAMPLE_SUMMARY, SAMPLE_POSITIONS, "2026-03-17T10:00:00Z")
        assert "-100.00" in output

    def test_empty_summary_no_crash(self):
        output = format_portfolio({}, [], "2026-03-17T10:00:00Z")
        assert "Trading212 Portfolio" in output

    def test_missing_investments_no_crash(self):
        output = format_portfolio({"totalValue": 0.0}, [], "2026-03-17T10:00:00Z")
        assert "0.00" in output


# ── main (script) ─────────────────────────────────────────────────────────────

ENV_WITH_CREDS = {"TRADING_212_API_KEY": "test-key", "TRADING_212_API_SECRET": "test-secret"}


class TestMain:
    def test_exits_when_api_key_missing(self):
        with patch.dict("os.environ", {}, clear=True):
            with patch("sys.argv", ["fetch_portfolio.py"]):
                with pytest.raises(SystemExit) as exc_info:
                    fetch_portfolio.main()
        assert exc_info.value.code == 1

    def test_exits_when_api_secret_missing(self):
        with patch.dict("os.environ", {"TRADING_212_API_KEY": "key"}, clear=True):
            with patch("sys.argv", ["fetch_portfolio.py"]):
                with pytest.raises(SystemExit) as exc_info:
                    fetch_portfolio.main()
        assert exc_info.value.code == 1

    def test_writes_json_and_prints_path_and_summary(self, tmp_path, capsys):
        with (
            patch.dict("os.environ", ENV_WITH_CREDS),
            patch.object(fetch_portfolio, "TMP_DIR", tmp_path),
            patch("get_stock_portfolio_fetch_portfolio.make_client") as mock_make,
            patch(
                "get_stock_portfolio_fetch_portfolio.fetch_account_summary",
                return_value=SAMPLE_SUMMARY,
            ),
            patch(
                "get_stock_portfolio_fetch_portfolio.fetch_positions",
                return_value=SAMPLE_POSITIONS,
            ),
        ):
            mock_make.return_value = MagicMock()
            with patch("sys.argv", ["fetch_portfolio.py"]):
                fetch_portfolio.main()

        captured = capsys.readouterr()
        lines = captured.out.strip().splitlines()

        output_path = Path(lines[0])
        assert output_path.exists()
        assert output_path.suffix == ".json"

        data = json.loads(output_path.read_text())
        assert data["account_summary"] == SAMPLE_SUMMARY
        assert data["positions"] == SAMPLE_POSITIONS
        assert "fetched_at" in data

        full_output = captured.out
        assert "Trading212 Portfolio" in full_output
        assert "Apple" in full_output

    def test_api_credentials_passed_to_make_client(self, tmp_path):
        with (
            patch.dict(
                "os.environ",
                {"TRADING_212_API_KEY": "my-key", "TRADING_212_API_SECRET": "my-secret"},
            ),
            patch.object(fetch_portfolio, "TMP_DIR", tmp_path),
            patch("get_stock_portfolio_fetch_portfolio.make_client") as mock_make,
            patch(
                "get_stock_portfolio_fetch_portfolio.fetch_account_summary",
                return_value=SAMPLE_SUMMARY,
            ),
            patch(
                "get_stock_portfolio_fetch_portfolio.fetch_positions",
                return_value=SAMPLE_POSITIONS,
            ),
        ):
            mock_make.return_value = MagicMock()
            with patch("sys.argv", ["fetch_portfolio.py"]):
                fetch_portfolio.main()

        mock_make.assert_called_once_with("my-key", "my-secret")

    def test_exits_on_api_error(self, tmp_path):
        with (
            patch.dict("os.environ", ENV_WITH_CREDS),
            patch.object(fetch_portfolio, "TMP_DIR", tmp_path),
            patch("get_stock_portfolio_fetch_portfolio.make_client") as mock_make,
            patch(
                "get_stock_portfolio_fetch_portfolio.fetch_account_summary",
                side_effect=requests.HTTPError("401"),
            ),
        ):
            mock_make.return_value = MagicMock()
            with patch("sys.argv", ["fetch_portfolio.py"]):
                with pytest.raises(SystemExit) as exc_info:
                    fetch_portfolio.main()

        assert exc_info.value.code == 1

    def test_no_file_written_on_error(self, tmp_path):
        with (
            patch.dict("os.environ", ENV_WITH_CREDS),
            patch.object(fetch_portfolio, "TMP_DIR", tmp_path),
            patch("get_stock_portfolio_fetch_portfolio.make_client") as mock_make,
            patch(
                "get_stock_portfolio_fetch_portfolio.fetch_account_summary",
                side_effect=RuntimeError("network error"),
            ),
        ):
            mock_make.return_value = MagicMock()
            with patch("sys.argv", ["fetch_portfolio.py"]):
                with pytest.raises(SystemExit):
                    fetch_portfolio.main()

        assert list(tmp_path.iterdir()) == []

    def test_creates_tmp_dir_if_missing(self, tmp_path):
        nested = tmp_path / "nested" / "tmp"
        with (
            patch.dict("os.environ", ENV_WITH_CREDS),
            patch.object(fetch_portfolio, "TMP_DIR", nested),
            patch("get_stock_portfolio_fetch_portfolio.make_client") as mock_make,
            patch(
                "get_stock_portfolio_fetch_portfolio.fetch_account_summary",
                return_value=SAMPLE_SUMMARY,
            ),
            patch(
                "get_stock_portfolio_fetch_portfolio.fetch_positions",
                return_value=SAMPLE_POSITIONS,
            ),
        ):
            mock_make.return_value = MagicMock()
            with patch("sys.argv", ["fetch_portfolio.py"]):
                fetch_portfolio.main()

        assert nested.exists()
