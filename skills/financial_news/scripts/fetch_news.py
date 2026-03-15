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
from html.parser import HTMLParser
from pathlib import Path

import feedparser
from common.args import base_parser
from common.logger import get_logger, setup

FEEDS = {
    "MarketWatch Top Stories": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
    "Yahoo Finance - Markets": "https://finance.yahoo.com/rss/2.0/headline?s=%5EGSPC,%5EDJI,%5EIXIC&region=US&lang=en-US",
    "CNBC Top News": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
    "Investing.com - Crypto News": "https://www.investing.com/rss/news_301.rss",
    "Investing.com - Crypto Opinion": "https://www.investing.com/rss/302.rss",
    "Investing.com - Investing Ideas": "https://www.investing.com/rss/market_overview_investing_ideas.rss",
    "Investing.com - Earnings Reports & Whispers": "https://www.investing.com/rss/news_1062.rss",
    "Investing.com - Earnings Call Transcripts": "https://www.investing.com/rss/news_1063.rss",
    "Investing.com - Stock Picks": "https://www.investing.com/rss/stock_stock_picks.rss",
    "The Motley Fool": "https://www.fool.com/a/feeds/partner/googlechromefollow?apikey=5e092c1f-c5f9-4428-9219-908a47d2e2de",
}

TMP_DIR = Path(__file__).parent.parent / "tmp"


class _HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def get_text(self) -> str:
        return " ".join(self._parts).strip()


def strip_html(text: str) -> str:
    if not text:
        return ""
    stripper = _HTMLStripper()
    stripper.feed(text)
    return stripper.get_text()


def fetch_feed(name: str, url: str, since: time.struct_time) -> list[dict]:
    logger = get_logger()
    logger.debug(f"fetching feed: {name}")
    feed = feedparser.parse(url)

    if feed.bozo and not feed.entries:
        logger.error(f"{name}: failed to parse — {feed.bozo_exception}")
        return []

    articles = []
    for entry in feed.entries:
        published = entry.get("published_parsed")

        if published is None or published < since:
            continue

        articles.append(
            {
                "title": entry.get("title", "").strip(),
                "summary": strip_html(entry.get("summary", "")),
                "url": entry.get("link", ""),
                "published_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", published),
                "source": name,
            }
        )

    logger.debug(f"{name}: {len(articles)} articles matched")
    return articles


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

    # sort all articles newest-first across all sources
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
