"""Tests for scripts/extract_tickers.py and daily_pipeline.tickers."""

import json
import logging
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import extract_tickers as extract_tickers_script
from daily_pipeline.tickers import extract_tickers, load_ticker_map


@pytest.fixture(autouse=True)
def reset_logger():
    yield
    logging.getLogger("finance_agent").handlers.clear()


TICKER_MAP = {"amazon": "AMZN", "apple": "AAPL", "nvidia": "NVDA", "meta": "META"}


def article(title, summary="", url="https://example.com/a"):
    return {"title": title, "summary": summary, "url": url}


# ── load_ticker_map ───────────────────────────────────────────────────────────


class TestLoadTickerMap:
    def test_loads_and_normalises(self, tmp_path):
        path = tmp_path / "map.json"
        path.write_text(json.dumps({"map": {"Amazon": "amzn", "APPLE": "AAPL"}}))
        result = load_ticker_map(path)
        assert result == {"amazon": "AMZN", "apple": "AAPL"}

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_ticker_map(tmp_path / "nope.json")

    def test_default_map_loads(self):
        result = load_ticker_map()
        assert result["amazon"] == "AMZN"


# ── extract_tickers ───────────────────────────────────────────────────────────


class TestExtractTickers:
    def test_cashtag_match(self):
        result = extract_tickers([article("$AMZN rallies")], TICKER_MAP)
        assert result[0]["symbol"] == "AMZN"
        assert result[0]["mentions"] == 1

    def test_bare_symbol_match(self):
        result = extract_tickers([article("NVDA hits new high")], TICKER_MAP)
        assert result[0]["symbol"] == "NVDA"

    def test_company_name_match_case_insensitive(self):
        result = extract_tickers([article("amazon beats estimates")], TICKER_MAP)
        assert result[0]["symbol"] == "AMZN"

    def test_unknown_uppercase_word_not_counted(self):
        result = extract_tickers([article("THE FED holds RATES")], TICKER_MAP)
        assert result == []

    def test_one_mention_per_article(self):
        result = extract_tickers([article("Amazon Amazon $AMZN AMZN")], TICKER_MAP)
        assert result[0]["mentions"] == 1

    def test_ranking_and_top_n(self):
        articles = [
            article("Amazon up", url="u1"),
            article("Amazon and Apple", url="u2"),
            article("Apple event", url="u3"),
            article("Nvidia earnings", url="u4"),
        ]
        result = extract_tickers(articles, TICKER_MAP, top_n=2)
        assert [r["symbol"] for r in result] == ["AAPL", "AMZN"]
        assert result[0]["mentions"] == 2

    def test_tie_breaks_alphabetically(self):
        result = extract_tickers([article("Amazon and Apple")], TICKER_MAP)
        assert [r["symbol"] for r in result] == ["AAPL", "AMZN"]

    def test_collects_article_urls(self):
        result = extract_tickers([article("Amazon up", url="u1")], TICKER_MAP)
        assert result[0]["articles"] == ["u1"]

    def test_empty_articles(self):
        assert extract_tickers([], TICKER_MAP) == []


# ── script main ───────────────────────────────────────────────────────────────


class TestMain:
    def test_writes_output_and_prints_path(self, tmp_path, capsys):
        analysis = tmp_path / "analysis.json"
        analysis.write_text(json.dumps([article("Amazon surges")]))
        map_path = tmp_path / "map.json"
        map_path.write_text(json.dumps({"map": TICKER_MAP}))

        argv = ["extract_tickers.py", "--input", str(analysis), "--map", str(map_path)]
        with (
            patch.object(extract_tickers_script, "TMP_DIR", tmp_path / "out"),
            patch.object(sys, "argv", argv),
        ):
            extract_tickers_script.main()

        output_path = Path(capsys.readouterr().out.strip())
        assert output_path.exists()
        results = json.loads(output_path.read_text())
        assert results[0]["symbol"] == "AMZN"

    def test_missing_input_exits_nonzero(self, tmp_path):
        argv = ["extract_tickers.py", "--input", str(tmp_path / "nope.json")]
        with patch.object(sys, "argv", argv), pytest.raises(SystemExit) as excinfo:
            extract_tickers_script.main()
        assert excinfo.value.code == 1
