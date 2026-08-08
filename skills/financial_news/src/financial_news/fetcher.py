"""
Financial news fetching logic.

Provides feed definitions and article fetching from RSS sources.
"""

import re
import time
from html.parser import HTMLParser

import feedparser
from common.logger import get_logger

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


def dedup_articles(articles: list[dict]) -> list[dict]:
    """Drop articles that appear in more than one feed.

    The same story is frequently syndicated across feeds (six of the feeds are
    Investing.com), and each copy would count as a separate ticker mention
    downstream. Match on URL first, then on normalised title; keep the first
    occurrence in fetch order.
    """
    logger = get_logger()
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    unique: list[dict] = []
    for article in articles:
        url = (article.get("url") or "").strip().rstrip("/").lower()
        title = re.sub(r"\W+", " ", (article.get("title") or "").lower()).strip()
        if (url and url in seen_urls) or (title and title in seen_titles):
            continue
        if url:
            seen_urls.add(url)
        if title:
            seen_titles.add(title)
        unique.append(article)
    logger.debug(f"deduped {len(articles) - len(unique)} of {len(articles)} articles")
    return unique
