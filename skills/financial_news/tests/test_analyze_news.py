"""Tests for skills/financial_news/scripts/analyze_news.py and financial_news.analyzer."""

import json
import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import analyze_news
from financial_news.analyzer import (
    analyse,
    compute_keyword_score,
    find_latest_news,
    load_keywords,
)


@pytest.fixture(autouse=True)
def reset_logger():
    yield
    logging.getLogger("finance_agent").handlers.clear()


SAMPLE_ARTICLES = [
    {
        "title": "Bitcoin surges 10% amid ETF approval rumours",
        "summary": "Crypto markets rallied as investors anticipated ETF approval.",
        "url": "https://example.com/1",
        "published_at": "2026-03-15T14:00:00Z",
        "source": "CNBC",
    },
    {
        "title": "Fed holds interest rates steady",
        "summary": "The Federal Reserve kept rates unchanged at its March meeting.",
        "url": "https://example.com/2",
        "published_at": "2026-03-15T13:00:00Z",
        "source": "MarketWatch",
    },
    {
        "title": "Apple earnings beat expectations",
        "summary": "Apple reported record quarterly earnings driven by iPhone sales.",
        "url": "https://example.com/3",
        "published_at": "2026-03-15T12:00:00Z",
        "source": "Yahoo Finance",
    },
]


# ── find_latest_news ──────────────────────────────────────────────────────────


class TestFindLatestNews:
    def test_returns_most_recent_file(self, tmp_path):
        (tmp_path / "news_results_20260315_120000.json").touch()
        (tmp_path / "news_results_20260315_140000.json").touch()
        result = find_latest_news(tmp_path)
        assert result.name == "news_results_20260315_140000.json"

    def test_raises_when_no_files(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="No news_results"):
            find_latest_news(tmp_path)


# ── load_keywords ─────────────────────────────────────────────────────────────


class TestLoadKeywords:
    def test_returns_lowercased_keywords(self, tmp_path):
        cfg = tmp_path / "keywords.json"
        cfg.write_text(json.dumps({"keywords": ["Bitcoin", "ETF", "Fed"]}))
        result = load_keywords(cfg)
        assert result == ["bitcoin", "etf", "fed"]

    def test_strips_whitespace(self, tmp_path):
        cfg = tmp_path / "keywords.json"
        cfg.write_text(json.dumps({"keywords": ["  bitcoin  ", " etf"]}))
        result = load_keywords(cfg)
        assert result == ["bitcoin", "etf"]

    def test_raises_on_empty_keywords(self, tmp_path):
        cfg = tmp_path / "keywords.json"
        cfg.write_text(json.dumps({"keywords": []}))
        with pytest.raises(ValueError, match="No keywords defined"):
            load_keywords(cfg)

    def test_raises_on_missing_keywords_key(self, tmp_path):
        cfg = tmp_path / "keywords.json"
        cfg.write_text(json.dumps({}))
        with pytest.raises(ValueError, match="No keywords defined"):
            load_keywords(cfg)

    def test_ignores_blank_entries(self, tmp_path):
        cfg = tmp_path / "keywords.json"
        cfg.write_text(json.dumps({"keywords": ["bitcoin", "  ", ""]}))
        result = load_keywords(cfg)
        assert result == ["bitcoin"]


# ── compute_keyword_score ─────────────────────────────────────────────────────


class TestComputeKeywordScore:
    def test_matches_at_cap_score_one(self):
        score, matched = compute_keyword_score(
            "bitcoin etf fed rally", ["bitcoin", "etf", "fed", "gold"]
        )
        assert score == 1.0
        assert set(matched) == {"bitcoin", "etf", "fed"}

    def test_no_keywords_matched(self):
        score, matched = compute_keyword_score("apple earnings beat", ["bitcoin", "etf"])
        assert score == 0.0
        assert matched == []

    def test_single_match_is_one_third(self):
        score, matched = compute_keyword_score("bitcoin rally", ["bitcoin", "etf", "fed"])
        assert score == pytest.approx(1 / 3, abs=0.001)
        assert matched == ["bitcoin"]

    def test_two_matches_is_two_thirds(self):
        score, matched = compute_keyword_score("bitcoin etf rally", ["bitcoin", "etf", "fed"])
        assert score == pytest.approx(2 / 3, abs=0.001)
        assert set(matched) == {"bitcoin", "etf"}

    def test_score_independent_of_keyword_list_size(self):
        many = [f"kw{i}" for i in range(10)] + ["bitcoin"]
        score_many, _ = compute_keyword_score("bitcoin rally", many)
        score_few, _ = compute_keyword_score("bitcoin rally", ["bitcoin", "etf"])
        assert score_many == score_few

    def test_matches_beyond_cap_still_one(self):
        keywords = ["bitcoin", "etf", "fed", "gold", "oil"]
        score, matched = compute_keyword_score("bitcoin etf fed gold oil", keywords)
        assert score == 1.0
        assert len(matched) == 5

    def test_case_insensitive(self):
        score, matched = compute_keyword_score("BITCOIN ETF", ["bitcoin", "etf"])
        assert score == pytest.approx(2 / 3, abs=0.001)
        assert set(matched) == {"bitcoin", "etf"}

    def test_score_rounded_to_4dp(self):
        score, _ = compute_keyword_score("bitcoin", ["bitcoin", "etf", "fed"])
        assert score == round(1 / 3, 4)


# ── analyse ───────────────────────────────────────────────────────────────────


class TestAnalyse:
    def test_returns_ranked_articles(self):
        import torch

        keywords = ["bitcoin", "etf"]
        query_vec = torch.tensor([1.0, 0.0])
        article_vecs = torch.tensor([[0.99, 0.01], [0.1, 0.99], [0.5, 0.5]])

        mock_model = MagicMock()
        mock_model.encode.side_effect = [query_vec, article_vecs]

        with patch("financial_news.analyzer.SentenceTransformer", return_value=mock_model):
            results = analyse(SAMPLE_ARTICLES, keywords)

        assert len(results) == 3
        assert results[0]["rank"] == 1
        assert results[0]["semantic_score"] >= results[1]["semantic_score"]
        assert results[1]["semantic_score"] >= results[2]["semantic_score"]

    def test_ranks_are_sequential(self):
        import torch

        keywords = ["bitcoin"]
        query_vec = torch.tensor([1.0, 0.0])
        article_vecs = torch.tensor([[0.9, 0.1], [0.5, 0.5], [0.2, 0.8]])

        mock_model = MagicMock()
        mock_model.encode.side_effect = [query_vec, article_vecs]

        with patch("financial_news.analyzer.SentenceTransformer", return_value=mock_model):
            results = analyse(SAMPLE_ARTICLES, keywords)

        assert [r["rank"] for r in results] == [1, 2, 3]

    def test_preserves_original_article_fields(self):
        import torch

        keywords = ["bitcoin"]
        query_vec = torch.tensor([1.0, 0.0])
        article_vecs = torch.tensor([[0.9, 0.1], [0.5, 0.5], [0.2, 0.8]])

        mock_model = MagicMock()
        mock_model.encode.side_effect = [query_vec, article_vecs]

        with patch("financial_news.analyzer.SentenceTransformer", return_value=mock_model):
            results = analyse(SAMPLE_ARTICLES, keywords)

        titles = {r["title"] for r in results}
        assert titles == {a["title"] for a in SAMPLE_ARTICLES}

    def test_matched_keywords_present(self):
        import torch

        keywords = ["bitcoin", "etf"]
        query_vec = torch.tensor([1.0, 0.0])
        article_vecs = torch.tensor([[0.9, 0.1], [0.5, 0.5], [0.2, 0.8]])

        mock_model = MagicMock()
        mock_model.encode.side_effect = [query_vec, article_vecs]

        with patch("financial_news.analyzer.SentenceTransformer", return_value=mock_model):
            results = analyse(SAMPLE_ARTICLES, keywords)

        bitcoin_article = next(r for r in results if "bitcoin" in r["title"].lower())
        assert "bitcoin" in bitcoin_article["matched_keywords"]
        assert "etf" in bitcoin_article["matched_keywords"]

    def test_semantic_score_clamped_to_0_1(self):
        import torch

        keywords = ["bitcoin"]
        query_vec = torch.tensor([1.0, 0.0])
        article_vecs = torch.tensor([[1.01, 0.0], [0.5, 0.5], [0.2, 0.8]])

        mock_model = MagicMock()
        mock_model.encode.side_effect = [query_vec, article_vecs]

        with patch("financial_news.analyzer.SentenceTransformer", return_value=mock_model):
            results = analyse(SAMPLE_ARTICLES, keywords)

        for r in results:
            assert 0.0 <= r["semantic_score"] <= 1.0


# ── main ──────────────────────────────────────────────────────────────────────


class TestMain:
    def _make_config(self, tmp_path):
        cfg = tmp_path / "keywords.json"
        cfg.write_text(json.dumps({"keywords": ["bitcoin", "etf"]}))
        return cfg

    def _make_news_file(self, tmp_path):
        news = tmp_path / "news_results_20260315_140000.json"
        news.write_text(json.dumps(SAMPLE_ARTICLES))
        return news

    def _mock_model(self):
        import torch

        mock_model = MagicMock()
        query_vec = torch.tensor([1.0, 0.0])
        article_vecs = torch.tensor([[0.9, 0.1], [0.5, 0.5], [0.2, 0.8]])
        mock_model.encode.side_effect = [query_vec, article_vecs]
        return mock_model

    def test_writes_output_file(self, tmp_path):
        cfg = self._make_config(tmp_path)
        news = self._make_news_file(tmp_path)
        with (
            patch.object(analyze_news, "TMP_DIR", tmp_path),
            patch.object(analyze_news, "DEFAULT_CONFIG", cfg),
            patch("financial_news.analyzer.SentenceTransformer", return_value=self._mock_model()),
            patch("sys.argv", ["analyze_news.py", "--input", str(news)]),
        ):
            analyze_news.main()

        output_files = list(tmp_path.glob("analysis_*.json"))
        assert len(output_files) == 1
        data = json.loads(output_files[0].read_text())
        assert len(data) == 3

    def test_output_is_valid_json_with_expected_fields(self, tmp_path):
        cfg = self._make_config(tmp_path)
        news = self._make_news_file(tmp_path)
        with (
            patch.object(analyze_news, "TMP_DIR", tmp_path),
            patch.object(analyze_news, "DEFAULT_CONFIG", cfg),
            patch("financial_news.analyzer.SentenceTransformer", return_value=self._mock_model()),
            patch("sys.argv", ["analyze_news.py", "--input", str(news)]),
        ):
            analyze_news.main()

        data = json.loads(list(tmp_path.glob("analysis_*.json"))[0].read_text())
        for article in data:
            assert "keyword_score" in article
            assert "semantic_score" in article
            assert "matched_keywords" in article
            assert "rank" in article

    def test_prints_output_path(self, tmp_path, capsys):
        cfg = self._make_config(tmp_path)
        news = self._make_news_file(tmp_path)
        with (
            patch.object(analyze_news, "TMP_DIR", tmp_path),
            patch.object(analyze_news, "DEFAULT_CONFIG", cfg),
            patch("financial_news.analyzer.SentenceTransformer", return_value=self._mock_model()),
            patch("sys.argv", ["analyze_news.py", "--input", str(news)]),
        ):
            analyze_news.main()

        captured = capsys.readouterr()
        assert "analysis_" in captured.out
        assert captured.out.strip().endswith(".json")

    def test_debug_flag_accepted(self, tmp_path):
        cfg = self._make_config(tmp_path)
        news = self._make_news_file(tmp_path)
        with (
            patch.object(analyze_news, "TMP_DIR", tmp_path),
            patch.object(analyze_news, "DEFAULT_CONFIG", cfg),
            patch("financial_news.analyzer.SentenceTransformer", return_value=self._mock_model()),
            patch("sys.argv", ["analyze_news.py", "--input", str(news), "--debug"]),
        ):
            analyze_news.main()

    def test_min_semantic_filters_articles(self, tmp_path):
        cfg = self._make_config(tmp_path)
        news = self._make_news_file(tmp_path)
        # mock_model returns scores ~[0.9, 0.5, 0.2]; --min-semantic 0.6 should keep only rank 1
        with (
            patch.object(analyze_news, "TMP_DIR", tmp_path),
            patch.object(analyze_news, "DEFAULT_CONFIG", cfg),
            patch("financial_news.analyzer.SentenceTransformer", return_value=self._mock_model()),
            patch("sys.argv", ["analyze_news.py", "--input", str(news), "--min-semantic", "0.6"]),
        ):
            analyze_news.main()

        data = json.loads(list(tmp_path.glob("analysis_*.json"))[0].read_text())
        assert all(a["semantic_score"] >= 0.6 for a in data)
        assert len(data) < 3

    def test_min_keyword_filters_articles(self, tmp_path):
        cfg = self._make_config(tmp_path)
        news = self._make_news_file(tmp_path)
        with (
            patch.object(analyze_news, "TMP_DIR", tmp_path),
            patch.object(analyze_news, "DEFAULT_CONFIG", cfg),
            patch("financial_news.analyzer.SentenceTransformer", return_value=self._mock_model()),
            patch("sys.argv", ["analyze_news.py", "--input", str(news), "--min-keyword", "0.5"]),
        ):
            analyze_news.main()

        data = json.loads(list(tmp_path.glob("analysis_*.json"))[0].read_text())
        assert all(a["keyword_score"] >= 0.5 for a in data)

    def test_min_semantic_and_min_keyword_combined(self, tmp_path):
        cfg = self._make_config(tmp_path)
        news = self._make_news_file(tmp_path)
        with (
            patch.object(analyze_news, "TMP_DIR", tmp_path),
            patch.object(analyze_news, "DEFAULT_CONFIG", cfg),
            patch("financial_news.analyzer.SentenceTransformer", return_value=self._mock_model()),
            patch(
                "sys.argv",
                [
                    "analyze_news.py",
                    "--input",
                    str(news),
                    "--min-semantic",
                    "0.4",
                    "--min-keyword",
                    "0.5",
                ],
            ),
        ):
            analyze_news.main()

        data = json.loads(list(tmp_path.glob("analysis_*.json"))[0].read_text())
        assert all(a["semantic_score"] >= 0.4 and a["keyword_score"] >= 0.5 for a in data)
