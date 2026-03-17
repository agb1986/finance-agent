"""
Analyse and rank financial news articles from the most recent fetch result.

Output file: skills/financial_news/tmp/analysis_<timestamp>.json

Usage:
    uv run skills/financial_news/scripts/analyze_news.py
    uv run skills/financial_news/scripts/analyze_news.py --config path/to/keywords.json
    uv run skills/financial_news/scripts/analyze_news.py --input path/to/news_results.json
    uv run skills/financial_news/scripts/analyze_news.py --min-semantic 0.40 --min-keyword 0.0
    uv run skills/financial_news/scripts/analyze_news.py --debug
"""

import argparse
import json
import time
from pathlib import Path

from common.args import base_parser
from common.logger import setup
from financial_news.analyzer import analyse, find_latest_news, load_keywords

TMP_DIR = Path(__file__).parent.parent / "tmp"
DEFAULT_CONFIG = Path(__file__).parent.parent / "keywords.json"


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
    parser.add_argument(
        "--min-semantic",
        type=float,
        default=None,
        metavar="SCORE",
        help="Only include articles with semantic_score >= SCORE (e.g. 0.40)",
    )
    parser.add_argument(
        "--min-keyword",
        type=float,
        default=None,
        metavar="SCORE",
        help="Only include articles with keyword_score >= SCORE (e.g. 0.0)",
    )
    args = parser.parse_args()

    logger = setup(args.debug)

    input_path = args.input or find_latest_news(TMP_DIR)
    logger.debug(f"reading articles from {input_path}")

    with input_path.open() as f:
        articles = json.load(f)
    logger.debug(f"loaded {len(articles)} articles")

    keywords = load_keywords(args.config)
    logger.debug(f"loaded {len(keywords)} keywords")

    results = analyse(articles, keywords)

    if args.min_semantic is not None:
        results = [r for r in results if r["semantic_score"] >= args.min_semantic]
        logger.debug(f"after --min-semantic {args.min_semantic}: {len(results)} articles remain")

    if args.min_keyword is not None:
        results = [r for r in results if r["keyword_score"] >= args.min_keyword]
        logger.debug(f"after --min-keyword {args.min_keyword}: {len(results)} articles remain")

    TMP_DIR.mkdir(exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_path = TMP_DIR / f"analysis_{timestamp}.json"
    output_path.write_text(json.dumps(results, indent=2))

    logger.debug(f"wrote {len(results)} ranked articles to {output_path}")
    print(str(output_path))


if __name__ == "__main__":
    main()
