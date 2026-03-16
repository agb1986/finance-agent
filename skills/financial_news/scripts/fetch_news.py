"""
Fetch financial news from RSS feeds and write results to a timestamped JSON file.

Output file: skills/financial_news/tmp/news_results_<timestamp>.json

Usage:
    uv run skills/financial_news/scripts/fetch_news.py
    uv run skills/financial_news/scripts/fetch_news.py --hours 48
    uv run skills/financial_news/scripts/fetch_news.py --debug
"""

import argparse
import json
import time
from pathlib import Path

from common.args import base_parser
from common.logger import setup
from financial_news.fetcher import FEEDS, fetch_feed

TMP_DIR = Path(__file__).parent.parent / "tmp"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch financial news from RSS feeds",
        parents=[base_parser()],
    )
    parser.add_argument("--hours", type=int, default=24, help="Look back N hours (default: 24)")
    args = parser.parse_args()

    logger = setup(args.debug)
    logger.debug(f"looking back {args.hours}h")

    cutoff = time.gmtime(time.time() - args.hours * 3600)

    all_articles: list[dict] = []
    for name, url in FEEDS.items():
        articles = fetch_feed(name, url, cutoff)
        all_articles.extend(articles)

    all_articles.sort(key=lambda a: a["published_at"], reverse=True)
    logger.debug(f"total articles after sort: {len(all_articles)}")

    TMP_DIR.mkdir(exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_path = TMP_DIR / f"news_results_{timestamp}.json"
    output_path.write_text(json.dumps(all_articles, indent=2))

    logger.debug(f"wrote {len(all_articles)} articles to {output_path}")
    print(str(output_path))


if __name__ == "__main__":
    main()
