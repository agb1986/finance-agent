"""
Financial news analysis and ranking logic.

Scores articles using keyword matching and semantic similarity,
then ranks them by semantic score descending.
"""

import json
from pathlib import Path

from common.logger import get_logger
from sentence_transformers import SentenceTransformer, util

MODEL_NAME = "all-MiniLM-L6-v2"

# Matching this many keywords scores 1.0. A capped count keeps scores meaningful
# regardless of how many keywords are configured — with the old
# fraction-of-all-keywords formula, one hit out of 12 keywords scored 0.083 and
# thresholds like --min-keyword 0.5 were effectively unreachable.
KEYWORD_SCORE_CAP = 3


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

    Score is the number of distinct keywords found, capped at KEYWORD_SCORE_CAP
    and normalised to 0.0–1.0 (1 match = 1/3, 2 = 2/3, 3+ = 1.0).
    """
    text_lower = text.lower()
    matched = [kw for kw in keywords if kw in text_lower]
    score = min(len(matched), KEYWORD_SCORE_CAP) / KEYWORD_SCORE_CAP
    return round(score, 4), matched


def analyse(articles: list[dict], keywords: list[str]) -> list[dict]:
    """Score and rank articles using keyword matching and semantic similarity.

    Encodes all articles in a single batch for efficiency.
    Articles are returned sorted by semantic_score descending with a rank field.
    """
    logger = get_logger()

    logger.debug(f"loading model: {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME)

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
