"""Tests for fetch_portfolio.py, client.py, and formatter.py."""

import hashlib
import hmac
import importlib.util
import json
import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests
from get_crypto_portfolio.client import (
    _extract_result,
    _sign_request,
    fetch_user_balance,
    make_client,
)
from get_crypto_portfolio.formatter import _fmt_decimal, _fmt_float, format_portfolio

_spec = importlib.util.spec_from_file_location(
    "get_crypto_portfolio_fetch_portfolio",
    Path(__file__).parent.parent / "scripts" / "fetch_portfolio.py",
)
fetch_portfolio = importlib.util.module_from_spec(_spec)
sys.modules["get_crypto_portfolio_fetch_portfolio"] = fetch_portfolio
_spec.loader.exec_module(fetch_portfolio)


@pytest.fixture(autouse=True)
def reset_logger():
    yield
    logging.getLogger("finance_agent").handlers.clear()


# ── Sample data ────────────────────────────────────────────────────────────────

SAMPLE_POSITION_BALANCES = [
    {
        "instrument_name": "BTC",
        "quantity": "0.5",
        "market_value": "15250.00",
        "collateral_amount": "15000.00",
    },
    {
        "instrument_name": "ETH",
        "quantity": "2.0",
        "market_value": "4900.00",
        "collateral_amount": "5000.00",
    },
]

SAMPLE_BALANCES = [
    {
        "instrument_name": "USD",
        "total_cash_balance": "20000.00",
        "total_margin_balance": "20500.00",
        "total_available_balance": "18000.00",
        "total_session_unrealized_pnl": "500.00",
        "total_session_realized_pnl": "100.00",
        "position_balances": SAMPLE_POSITION_BALANCES,
    }
]


# ── client: make_client ────────────────────────────────────────────────────────


class TestMakeClient:
    def test_returns_http_client(self):
        from common.http_client import HttpClient

        client = make_client()
        assert isinstance(client, HttpClient)

    def test_base_url_is_crypto_com(self):
        client = make_client()
        assert "crypto.com" in client.base_url


# ── client: _sign_request ──────────────────────────────────────────────────────


class TestSignRequest:
    def test_contains_required_keys(self):
        body = _sign_request("private/user-balance", {}, "my-key", "my-secret")
        for key in ("id", "method", "api_key", "params", "nonce", "sig"):
            assert key in body

    def test_method_is_correct(self):
        body = _sign_request("private/user-balance", {}, "key", "secret")
        assert body["method"] == "private/user-balance"

    def test_api_key_is_set(self):
        body = _sign_request("private/user-balance", {}, "my-key", "my-secret")
        assert body["api_key"] == "my-key"

    def test_params_are_included(self):
        body = _sign_request("private/user-balance", {"foo": "bar"}, "k", "s")
        assert body["params"] == {"foo": "bar"}

    def test_signature_is_valid_hmac_sha256(self):
        api_key = "test-key"
        api_secret = "test-secret"
        method = "private/user-balance"
        body = _sign_request(method, {}, api_key, api_secret)

        params_str = ""  # empty params
        sig_payload = method + str(body["id"]) + api_key + params_str + str(body["nonce"])
        expected_sig = hmac.new(
            bytes(api_secret, "utf-8"),
            msg=bytes(sig_payload, "utf-8"),
            digestmod=hashlib.sha256,
        ).hexdigest()

        assert body["sig"] == expected_sig

    def test_params_sorted_alphabetically_in_signature(self):
        api_key = "k"
        api_secret = "s"
        method = "private/get-positions"
        params = {"z_param": "last", "a_param": "first"}
        body = _sign_request(method, params, api_key, api_secret)

        params_str = "a_paramfirstz_paramlast"
        sig_payload = method + str(body["id"]) + api_key + params_str + str(body["nonce"])
        expected_sig = hmac.new(
            bytes(api_secret, "utf-8"),
            msg=bytes(sig_payload, "utf-8"),
            digestmod=hashlib.sha256,
        ).hexdigest()

        assert body["sig"] == expected_sig


# ── client: _extract_result ────────────────────────────────────────────────────


class TestExtractResult:
    def test_returns_data_on_success(self):
        response = {"code": 0, "result": {"data": [{"key": "val"}]}}
        data = _extract_result(response, "private/user-balance")
        assert data == [{"key": "val"}]

    def test_raises_on_nonzero_code(self):
        response = {"code": 10001, "message": "Unauthorized"}
        with pytest.raises(RuntimeError, match="10001"):
            _extract_result(response, "private/user-balance")

    def test_raises_includes_message(self):
        response = {"code": 10004, "message": "Bad Request", "detail": "invalid sig"}
        with pytest.raises(RuntimeError, match="Bad Request"):
            _extract_result(response, "private/user-balance")

    def test_returns_result_when_no_data_key(self):
        response = {"code": 0, "result": {"foo": "bar"}}
        data = _extract_result(response, "private/user-balance")
        assert data == {"foo": "bar"}


# ── client: fetch_user_balance ─────────────────────────────────────────────────


class TestFetchUserBalance:
    def test_calls_post_with_correct_method(self):
        mock_client = MagicMock()
        mock_client.post.return_value = {"code": 0, "result": {"data": SAMPLE_BALANCES}}
        result = fetch_user_balance(mock_client, "key", "secret")
        assert mock_client.post.call_args[0][0] == "private/user-balance"
        assert result == SAMPLE_BALANCES

    def test_raises_on_api_error(self):
        mock_client = MagicMock()
        mock_client.post.return_value = {"code": 10001, "message": "Unauthorized"}
        with pytest.raises(RuntimeError):
            fetch_user_balance(mock_client, "key", "secret")


# ── formatter ──────────────────────────────────────────────────────────────────


class TestFormatPortfolio:
    def test_includes_date_in_header(self):
        output = format_portfolio(SAMPLE_BALANCES, SAMPLE_POSITION_BALANCES, "2026-03-17T10:00:00Z")
        assert "2026-03-17" in output

    def test_includes_currency(self):
        output = format_portfolio(SAMPLE_BALANCES, SAMPLE_POSITION_BALANCES, "2026-03-17T10:00:00Z")
        assert "USD" in output

    def test_includes_cash_balance(self):
        output = format_portfolio(SAMPLE_BALANCES, SAMPLE_POSITION_BALANCES, "2026-03-17T10:00:00Z")
        assert "20,000.00" in output

    def test_includes_position_instruments(self):
        output = format_portfolio(SAMPLE_BALANCES, SAMPLE_POSITION_BALANCES, "2026-03-17T10:00:00Z")
        assert "BTC" in output
        assert "ETH" in output

    def test_position_count_shown(self):
        output = format_portfolio(SAMPLE_BALANCES, SAMPLE_POSITION_BALANCES, "2026-03-17T10:00:00Z")
        assert "Open Positions (2)" in output

    def test_no_positions_message(self):
        output = format_portfolio(SAMPLE_BALANCES, [], "2026-03-17T10:00:00Z")
        assert "No open positions" in output

    def test_no_balance_message(self):
        output = format_portfolio([], [], "2026-03-17T10:00:00Z")
        assert "No balance data" in output

    def test_positions_sorted_by_market_value_descending(self):
        output = format_portfolio(SAMPLE_BALANCES, SAMPLE_POSITION_BALANCES, "2026-03-17T10:00:00Z")
        btc_idx = output.index("BTC")
        eth_idx = output.index("ETH")
        assert btc_idx < eth_idx  # BTC market_value=15250 > ETH market_value=4900

    def test_positive_pnl_has_plus_sign(self):
        output = format_portfolio(SAMPLE_BALANCES, SAMPLE_POSITION_BALANCES, "2026-03-17T10:00:00Z")
        assert "+250.00" in output  # BTC: 15250 - 15000 = +250

    def test_negative_pnl_no_plus_sign(self):
        output = format_portfolio(SAMPLE_BALANCES, SAMPLE_POSITION_BALANCES, "2026-03-17T10:00:00Z")
        assert "-100.00" in output  # ETH: 4900 - 5000 = -100
        assert "+-100.00" not in output

    def test_empty_balances_no_crash(self):
        output = format_portfolio([], [], "2026-03-17T10:00:00Z")
        assert "Crypto.com Portfolio" in output


class TestFmtFloat:
    def test_formats_string(self):
        assert _fmt_float("1234.5") == "1,234.50"

    def test_formats_float(self):
        assert _fmt_float(99.9) == "99.90"

    def test_formats_int(self):
        assert _fmt_float(0) == "0.00"

    def test_invalid_returns_string(self):
        assert _fmt_float("n/a") == "n/a"


class TestFmtDecimal:
    def test_strips_trailing_zeros(self):
        assert _fmt_decimal("0.0015775", decimals=7) == "0.0015775"

    def test_whole_number_no_dot(self):
        assert _fmt_decimal("1.0", decimals=7) == "1"

    def test_custom_decimals(self):
        assert _fmt_decimal("1.12345", decimals=4) == "1.1235"

    def test_invalid_returns_string(self):
        assert _fmt_decimal("n/a") == "n/a"


class TestFormatPortfolioQuantity:
    def test_quantity_shows_7_decimal_places(self):
        positions = [
            {
                "instrument_name": "BTC",
                "quantity": "0.0015775",
                "market_value": "116.96",
                "collateral_amount": "109.65",
            }
        ]
        output = format_portfolio([], positions, "2026-03-17T10:00:00Z")
        assert "0.0015775" in output


# ── main (script) ──────────────────────────────────────────────────────────────

ENV_WITH_CREDS = {"CRYPTO_API_KEY": "test-key", "CRYPTO_API_SECRET": "test-secret"}


class TestMain:
    def test_exits_when_api_key_missing(self):
        with patch.dict("os.environ", {}, clear=True):
            with patch("sys.argv", ["fetch_portfolio.py"]):
                with pytest.raises(SystemExit) as exc_info:
                    fetch_portfolio.main()
        assert exc_info.value.code == 1

    def test_exits_when_api_secret_missing(self):
        with patch.dict("os.environ", {"CRYPTO_API_KEY": "key"}, clear=True):
            with patch("sys.argv", ["fetch_portfolio.py"]):
                with pytest.raises(SystemExit) as exc_info:
                    fetch_portfolio.main()
        assert exc_info.value.code == 1

    def test_writes_json_and_prints_path_and_summary(self, tmp_path, capsys):
        with (
            patch.dict("os.environ", ENV_WITH_CREDS),
            patch.object(fetch_portfolio, "TMP_DIR", tmp_path),
            patch("get_crypto_portfolio_fetch_portfolio.make_client") as mock_make,
            patch(
                "get_crypto_portfolio_fetch_portfolio.fetch_user_balance",
                return_value=SAMPLE_BALANCES,
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
        assert data["balances"] == SAMPLE_BALANCES
        assert data["position_balances"] == SAMPLE_POSITION_BALANCES
        assert "fetched_at" in data

        full_output = captured.out
        assert "Crypto.com Portfolio" in full_output
        assert "BTC" in full_output

    def test_api_credentials_passed_to_fetch_functions(self, tmp_path):
        with (
            patch.dict(
                "os.environ", {"CRYPTO_API_KEY": "my-key", "CRYPTO_API_SECRET": "my-secret"}
            ),
            patch.object(fetch_portfolio, "TMP_DIR", tmp_path),
            patch("get_crypto_portfolio_fetch_portfolio.make_client") as mock_make,
            patch(
                "get_crypto_portfolio_fetch_portfolio.fetch_user_balance",
                return_value=SAMPLE_BALANCES,
            ) as mock_balance,
        ):
            mock_make.return_value = MagicMock()
            with patch("sys.argv", ["fetch_portfolio.py"]):
                fetch_portfolio.main()

        mock_balance.assert_called_once_with(mock_make.return_value, "my-key", "my-secret")

    def test_exits_on_api_error(self, tmp_path):
        with (
            patch.dict("os.environ", ENV_WITH_CREDS),
            patch.object(fetch_portfolio, "TMP_DIR", tmp_path),
            patch("get_crypto_portfolio_fetch_portfolio.make_client") as mock_make,
            patch(
                "get_crypto_portfolio_fetch_portfolio.fetch_user_balance",
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
            patch("get_crypto_portfolio_fetch_portfolio.make_client") as mock_make,
            patch(
                "get_crypto_portfolio_fetch_portfolio.fetch_user_balance",
                side_effect=RuntimeError("API error"),
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
            patch("get_crypto_portfolio_fetch_portfolio.make_client") as mock_make,
            patch(
                "get_crypto_portfolio_fetch_portfolio.fetch_user_balance",
                return_value=SAMPLE_BALANCES,
            ),
        ):
            mock_make.return_value = MagicMock()
            with patch("sys.argv", ["fetch_portfolio.py"]):
                fetch_portfolio.main()

        assert nested.exists()
