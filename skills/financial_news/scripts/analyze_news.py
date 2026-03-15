"""
Analyse and rank financial news articles from the most recent fetch result.

Scores each article using two independent signals:
  - keyword_score:  fraction of configured keywords matched in title + summary (0.0–1.0)
  - semantic_score: cosine similarity between the article text and a query built
                    from all configured keywords, using a local sentence-transformer
                    model (0.0–1.0)

Articles are ranked by semantic_score descending. Both scores are written to the
output alongside the list of matched keywords so the caller can inspect both signals.

Output file: skills/financial_news/tmp/analysis_{timestamp}.json

Usage:
    uv run skills/financial_news/scripts/analyze_news.py
    uv run skills/financial_news/scripts/analyze_news.py --config path/to/keywords.json
    uv run skills/financial_news/scripts/analyze_news.py --input path/to/news_results.json
    uv run skills/financial_news/scripts/analyze_news.py --debug
"""

import argparse
import json
import time
from pathlib import Path

from common.args import base_parser
from common.logger import get_logger, setup
from sentence_transformers import SentenceTransformer, util

TMP_DIR = Path(__file__).parent.parent / "tmp"
DEFAULT_CONFIG = Path(__file__).parent.parent / "keywords.json"
MODEL_NAME = "all-MiniLM-L6-v2"


def find_latest_news(tmp_dir: Path) -> Path:
    """Return the most recently created news_results JSON in tmp_dir."""
    files = sorted(tmp_dir.glob("news_results_*.json"), reverse=True)
    if not files:
        raise FileNotFoundError(f"No news_results_*.json found in {tmp_dir}")
    return files[0]


def load_keywords(config_path: Path) -> list[str]:
    """Load and validate keywords from the JSON config file."""
    with config_path.open() as f:
        data = json.load(f)
    keywords = [kw.strip().lower() for kw in data.get("keywords", []) if kw.strip()]
    if not keywords:
        raise ValueError(f"No keywords defined in {config_path} — add some before running analysis")
    return keywords


def compute_keyword_score(text: str, keywords: list[str]) -> tuple[float, list[str]]:
    """Return (score, matched_keywords) for the given text against the keyword list.

    Score is the fraction of keywords found in the text (0.0–1.0).
    """
    text_lower = text.lower()
    matched = [kw for kw in keywords if kw in text_lower]
    score = len(matched) / len(keywords)
    return round(score, 4), matched


def analyse(articles: list[dict], keywords: list[str]) -> list[dict]:
    """Score and rank articles using keyword matching and semantic similarity.

    Encodes all articles in a single batch for efficiency.
    Articles are returned sorted by semantic_score descending with a rank field.
    """
    logger = get_logger()

    logger.debug(f"loading model: {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME)

    # Build a natural-language query from the keywords for semantic matching
    query = ", ".join(keywords)
    logger.debug(f"encoding query: {query!r}")
    query_embedding = model.encode(query, convert_to_tensor=True)

    texts = [f"{a.get('title', '')} {a.get('summary', '')}".strip() for a in articles]

    logger.debug(f"encoding {len(texts)} articles in batch")
    article_embeddings = model.encode(texts, convert_to_tensor=True, show_progress_bar=False)

    results = []
    for i, article in enumerate(articles):
        kw_score, matched = compute_keyword_score(texts[i], keywords)

        sem_score = float(util.cos_sim(query_embedding, article_embeddings[i])[0][0])
        sem_score = round(max(0.0, min(1.0, sem_score)), 4)

        results.append(
            {
                **article,
                "keyword_score": kw_score,
                "semantic_score": sem_score,
                "matched_keywords": matched,
            }
        )

    results.sort(key=lambda a: a["semantic_score"], reverse=True)
    for rank, result in enumerate(results, 1):
        result["rank"] = rank

    logger.debug(f"ranked {len(results)} articles")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyse and rank financial news articles",
        parents=[base_parser()],
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help=f"Path to keywords JSON config (default: {DEFAULT_CONFIG})",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="Path to a specific news_results JSON (default: most recent in tmp/)",
    )
    args = parser.parse_args()

    logger = setup(args.debug)

    input_path = args.input or find_latest_news(TMP_DIR)
    logger.debug(f"reading articles from {input_path}")

    with input_path.open() as f:
        articles = json.load(f)
    logger.debug(f"loaded {len(articles)} articles")

    keywords = load_keywords(args.config)
    logger.debug(f"loaded {len(keywords)} keywords: {keywords}")

    results = analyse(articles, keywords)

    TMP_DIR.mkdir(exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_path = TMP_DIR / f"analysis_{timestamp}.json"
    output_path.write_text(json.dumps(results, indent=2))

    logger.debug(f"wrote {len(results)} ranked articles to {output_path}")
    print(str(output_path))


if __name__ == "__main__":
    main()
