"""Tests for fetch_quote.py"""

import json
import logging
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import fetch_quote


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


class TestMain:
    def test_writes_json_and_prints_path(self, tmp_path, capsys):
        with (
            patch.object(fetch_quote, "TMP_DIR", tmp_path),
            patch("fetch_quote.fetch_quote_data", return_value=SAMPLE_QUOTE),
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
            patch("fetch_quote.fetch_quote_data", return_value=SAMPLE_QUOTE) as mock_fetch,
        ):
            with patch("sys.argv", ["fetch_quote.py", "--symbol", "AMZN", "--market", "NASDAQ"]):
                fetch_quote.main()

        mock_fetch.assert_called_once_with("AMZN", "NASDAQ")

    def test_symbol_uppercased(self, tmp_path):
        with (
            patch.object(fetch_quote, "TMP_DIR", tmp_path),
            patch("fetch_quote.fetch_quote_data", return_value=SAMPLE_QUOTE) as mock_fetch,
        ):
            with patch("sys.argv", ["fetch_quote.py", "--symbol", "amzn"]):
                fetch_quote.main()

        mock_fetch.assert_called_once_with("AMZN", None)

    def test_exits_on_not_implemented(self, tmp_path):
        with (
            patch.object(fetch_quote, "TMP_DIR", tmp_path),
            patch("fetch_quote.fetch_quote_data", side_effect=NotImplementedError("stub")),
        ):
            with patch("sys.argv", ["fetch_quote.py", "--symbol", "AMZN"]):
                with pytest.raises(SystemExit) as exc_info:
                    fetch_quote.main()

        assert exc_info.value.code == 1

    def test_exits_on_fetch_error(self, tmp_path):
        with (
            patch.object(fetch_quote, "TMP_DIR", tmp_path),
            patch("fetch_quote.fetch_quote_data", side_effect=RuntimeError("API error")),
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
            patch("fetch_quote.fetch_quote_data", side_effect=RuntimeError("API error")),
        ):
            with patch("sys.argv", ["fetch_quote.py", "--symbol", "AMZN"]):
                with pytest.raises(SystemExit):
                    fetch_quote.main()

        assert list(tmp_path.iterdir()) == []

    def test_creates_tmp_dir_if_missing(self, tmp_path):
        nested = tmp_path / "nested" / "tmp"
        with (
            patch.object(fetch_quote, "TMP_DIR", nested),
            patch("fetch_quote.fetch_quote_data", return_value=SAMPLE_QUOTE),
        ):
            with patch("sys.argv", ["fetch_quote.py", "--symbol", "AMZN"]):
                fetch_quote.main()

        assert nested.exists()
