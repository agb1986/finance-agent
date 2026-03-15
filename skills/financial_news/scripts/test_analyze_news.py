"""Tests for analyze_news.py."""

import json
import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import analyze_news


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


# --- find_latest_news ---


class TestFindLatestNews:
    def test_returns_most_recent_file(self, tmp_path):
        (tmp_path / "news_results_20260315_120000.json").touch()
        (tmp_path / "news_results_20260315_140000.json").touch()
        result = analyze_news.find_latest_news(tmp_path)
        assert result.name == "news_results_20260315_140000.json"

    def test_raises_when_no_files(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="No news_results"):
            analyze_news.find_latest_news(tmp_path)


# --- load_keywords ---


class TestLoadKeywords:
    def test_returns_lowercased_keywords(self, tmp_path):
        cfg = tmp_path / "keywords.json"
        cfg.write_text(json.dumps({"keywords": ["Bitcoin", "ETF", "Fed"]}))
        result = analyze_news.load_keywords(cfg)
        assert result == ["bitcoin", "etf", "fed"]

    def test_strips_whitespace(self, tmp_path):
        cfg = tmp_path / "keywords.json"
        cfg.write_text(json.dumps({"keywords": ["  bitcoin  ", " etf"]}))
        result = analyze_news.load_keywords(cfg)
        assert result == ["bitcoin", "etf"]

    def test_raises_on_empty_keywords(self, tmp_path):
        cfg = tmp_path / "keywords.json"
        cfg.write_text(json.dumps({"keywords": []}))
        with pytest.raises(ValueError, match="No keywords defined"):
            analyze_news.load_keywords(cfg)

    def test_raises_on_missing_keywords_key(self, tmp_path):
        cfg = tmp_path / "keywords.json"
        cfg.write_text(json.dumps({}))
        with pytest.raises(ValueError, match="No keywords defined"):
            analyze_news.load_keywords(cfg)

    def test_ignores_blank_entries(self, tmp_path):
        cfg = tmp_path / "keywords.json"
        cfg.write_text(json.dumps({"keywords": ["bitcoin", "  ", ""]}))
        result = analyze_news.load_keywords(cfg)
        assert result == ["bitcoin"]


# --- compute_keyword_score ---


class TestComputeKeywordScore:
    def test_all_keywords_matched(self):
        score, matched = analyze_news.compute_keyword_score("bitcoin etf rally", ["bitcoin", "etf"])
        assert score == 1.0
        assert set(matched) == {"bitcoin", "etf"}

    def test_no_keywords_matched(self):
        score, matched = analyze_news.compute_keyword_score(
            "apple earnings beat", ["bitcoin", "etf"]
        )
        assert score == 0.0
        assert matched == []

    def test_partial_match(self):
        score, matched = analyze_news.compute_keyword_score(
            "bitcoin rally", ["bitcoin", "etf", "fed"]
        )
        assert score == pytest.approx(1 / 3, abs=0.001)
        assert matched == ["bitcoin"]

    def test_case_insensitive(self):
        score, matched = analyze_news.compute_keyword_score("BITCOIN ETF", ["bitcoin", "etf"])
        assert score == 1.0

    def test_score_rounded_to_4dp(self):
        score, _ = analyze_news.compute_keyword_score("bitcoin", ["bitcoin", "etf", "fed"])
        assert score == round(1 / 3, 4)


# --- analyse ---


class TestAnalyse:
    def _make_mock_model(self, query_vec, article_vecs):
        """Return a mock SentenceTransformer that returns preset embeddings."""
        model = MagicMock()
        # First call (query), then batch call (articles)
        model.encode.side_effect = [query_vec, article_vecs]
        return model

    def test_returns_ranked_articles(self):
        import torch

        keywords = ["bitcoin", "etf"]
        # Give article 0 a high cosine sim, article 1 low
        query_vec = torch.tensor([1.0, 0.0])
        article_vecs = torch.tensor([[0.99, 0.01], [0.1, 0.99], [0.5, 0.5]])

        mock_model = MagicMock()
        mock_model.encode.side_effect = [query_vec, article_vecs]

        with patch("analyze_news.SentenceTransformer", return_value=mock_model):
            results = analyze_news.analyse(SAMPLE_ARTICLES, keywords)

        assert len(results) == 3
        # rank 1 should have highest semantic score
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

        with patch("analyze_news.SentenceTransformer", return_value=mock_model):
            results = analyze_news.analyse(SAMPLE_ARTICLES, keywords)

        assert [r["rank"] for r in results] == [1, 2, 3]

    def test_preserves_original_article_fields(self):
        import torch

        keywords = ["bitcoin"]
        query_vec = torch.tensor([1.0, 0.0])
        article_vecs = torch.tensor([[0.9, 0.1], [0.5, 0.5], [0.2, 0.8]])

        mock_model = MagicMock()
        mock_model.encode.side_effect = [query_vec, article_vecs]

        with patch("analyze_news.SentenceTransformer", return_value=mock_model):
            results = analyze_news.analyse(SAMPLE_ARTICLES, keywords)

        titles = {r["title"] for r in results}
        assert titles == {a["title"] for a in SAMPLE_ARTICLES}

    def test_matched_keywords_present(self):
        import torch

        keywords = ["bitcoin", "etf"]
        query_vec = torch.tensor([1.0, 0.0])
        article_vecs = torch.tensor([[0.9, 0.1], [0.5, 0.5], [0.2, 0.8]])

        mock_model = MagicMock()
        mock_model.encode.side_effect = [query_vec, article_vecs]

        with patch("analyze_news.SentenceTransformer", return_value=mock_model):
            results = analyze_news.analyse(SAMPLE_ARTICLES, keywords)

        # The bitcoin/ETF article should have matched_keywords populated
        bitcoin_article = next(r for r in results if "bitcoin" in r["title"].lower())
        assert "bitcoin" in bitcoin_article["matched_keywords"]
        assert "etf" in bitcoin_article["matched_keywords"]

    def test_semantic_score_clamped_to_0_1(self):
        import torch

        keywords = ["bitcoin"]
        query_vec = torch.tensor([1.0, 0.0])
        # Simulate cos_sim returning a value slightly above 1.0 (floating point)
        article_vecs = torch.tensor([[1.01, 0.0], [0.5, 0.5], [0.2, 0.8]])

        mock_model = MagicMock()
        mock_model.encode.side_effect = [query_vec, article_vecs]

        with patch("analyze_news.SentenceTransformer", return_value=mock_model):
            results = analyze_news.analyse(SAMPLE_ARTICLES, keywords)

        for r in results:
            assert 0.0 <= r["semantic_score"] <= 1.0


# --- main ---


class TestMain:
    def _make_config(self, tmp_path):
        cfg = tmp_path / "keywords.json"
        cfg.write_text(json.dumps({"keywords": ["bitcoin", "etf"]}))
        return cfg

    def _make_news_file(self, tmp_path):
        news = tmp_path / "news_results_20260315_140000.json"
        news.write_text(json.dumps(SAMPLE_ARTICLES))
        return news

    def test_writes_output_file(self, tmp_path):
        import torch

        cfg = self._make_config(tmp_path)
        news = self._make_news_file(tmp_path)

        query_vec = torch.tensor([1.0, 0.0])
        article_vecs = torch.tensor([[0.9, 0.1], [0.5, 0.5], [0.2, 0.8]])
        mock_model = MagicMock()
        mock_model.encode.side_effect = [query_vec, article_vecs]

        with (
            patch("analyze_news.TMP_DIR", tmp_path),
            patch("analyze_news.DEFAULT_CONFIG", cfg),
            patch("analyze_news.SentenceTransformer", return_value=mock_model),
            patch("sys.argv", ["analyze_news.py", "--input", str(news)]),
        ):
            analyze_news.main()

        output_files = list(tmp_path.glob("analysis_*.json"))
        assert len(output_files) == 1
        data = json.loads(output_files[0].read_text())
        assert len(data) == 3

    def test_output_is_valid_json_with_expected_fields(self, tmp_path):
        import torch

        cfg = self._make_config(tmp_path)
        news = self._make_news_file(tmp_path)

        query_vec = torch.tensor([1.0, 0.0])
        article_vecs = torch.tensor([[0.9, 0.1], [0.5, 0.5], [0.2, 0.8]])
        mock_model = MagicMock()
        mock_model.encode.side_effect = [query_vec, article_vecs]

        with (
            patch("analyze_news.TMP_DIR", tmp_path),
            patch("analyze_news.DEFAULT_CONFIG", cfg),
            patch("analyze_news.SentenceTransformer", return_value=mock_model),
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
        import torch

        cfg = self._make_config(tmp_path)
        news = self._make_news_file(tmp_path)

        query_vec = torch.tensor([1.0, 0.0])
        article_vecs = torch.tensor([[0.9, 0.1], [0.5, 0.5], [0.2, 0.8]])
        mock_model = MagicMock()
        mock_model.encode.side_effect = [query_vec, article_vecs]

        with (
            patch("analyze_news.TMP_DIR", tmp_path),
            patch("analyze_news.DEFAULT_CONFIG", cfg),
            patch("analyze_news.SentenceTransformer", return_value=mock_model),
            patch("sys.argv", ["analyze_news.py", "--input", str(news)]),
        ):
            analyze_news.main()

        captured = capsys.readouterr()
        assert "analysis_" in captured.out
        assert captured.out.strip().endswith(".json")

    def test_debug_flag_accepted(self, tmp_path):
        import torch

        cfg = self._make_config(tmp_path)
        news = self._make_news_file(tmp_path)

        query_vec = torch.tensor([1.0, 0.0])
        article_vecs = torch.tensor([[0.9, 0.1], [0.5, 0.5], [0.2, 0.8]])
        mock_model = MagicMock()
        mock_model.encode.side_effect = [query_vec, article_vecs]

        with (
            patch("analyze_news.TMP_DIR", tmp_path),
            patch("analyze_news.DEFAULT_CONFIG", cfg),
            patch("analyze_news.SentenceTransformer", return_value=mock_model),
            patch("sys.argv", ["analyze_news.py", "--input", str(news), "--debug"]),
        ):
            analyze_news.main()  # should not raise
