"""Extract top stock-ticker mentions from analysed news articles.

Two matching layers, both validated against ticker_map.json so random uppercase
words never count as tickers:

1. Cashtags (``$AMZN``) and bare symbols (``AMZN``) — counted only when the
   symbol appears in the map's values.
2. Company names (``Amazon``) — case-insensitive word-boundary matches against
   the map's keys.
"""

import json
import re
from collections import defaultdict
from pathlib import Path

from common.logger import get_logger

SKILL_ROOT = Path(__file__).parent.parent.parent
DEFAULT_MAP_PATH = SKILL_ROOT / "ticker_map.json"

_CASHTAG_RE = re.compile(r"\$([A-Z]{1,5}(?:\.[A-Z])?)\b")
_SYMBOL_RE = re.compile(r"\b([A-Z]{2,5}(?:\.[A-Z])?)\b")


def load_ticker_map(path: Path | None = None) -> dict[str, str]:
    """Load the company-name → symbol map.

    Args:
        path: Optional alternative map path. Defaults to the skill-root ticker_map.json.

    Returns:
        Dict of lowercase company name → uppercase ticker symbol.

    Raises:
        FileNotFoundError: If the map file does not exist.
    """
    logger = get_logger()
    map_path = path or DEFAULT_MAP_PATH
    with map_path.open() as f:
        data = json.load(f)
    ticker_map = {name.lower(): symbol.upper() for name, symbol in data["map"].items()}
    logger.debug(f"loaded {len(ticker_map)} name→ticker entries from {map_path}")
    return ticker_map


def extract_tickers(
    articles: list[dict],
    ticker_map: dict[str, str],
    top_n: int = 5,
) -> list[dict]:
    """Count ticker mentions across articles and return the top N.

    Args:
        articles:   Article dicts with at least ``title`` and ``summary`` fields.
        ticker_map: Lowercase company name → symbol map (see load_ticker_map).
        top_n:      Number of tickers to return.

    Returns:
        List of ``{"symbol", "mentions", "articles"}`` dicts sorted by mention
        count descending, then symbol ascending for a stable order.
    """
    logger = get_logger()
    known_symbols = set(ticker_map.values())
    name_patterns = {
        name: re.compile(rf"\b{re.escape(name)}\b", re.IGNORECASE) for name in ticker_map
    }

    mentions: dict[str, int] = defaultdict(int)
    article_urls: dict[str, list[str]] = defaultdict(list)

    for article in articles:
        text = f"{article.get('title', '')} {article.get('summary', '')}"
        found: set[str] = set()

        for match in _CASHTAG_RE.findall(text):
            if match in known_symbols:
                found.add(match)
        for match in _SYMBOL_RE.findall(text):
            if match in known_symbols:
                found.add(match)
        for name, pattern in name_patterns.items():
            if pattern.search(text):
                found.add(ticker_map[name])

        url = article.get("url", "")
        for symbol in found:
            mentions[symbol] += 1
            if url:
                article_urls[symbol].append(url)

    ranked = sorted(mentions.items(), key=lambda item: (-item[1], item[0]))
    results = [
        {"symbol": symbol, "mentions": count, "articles": article_urls[symbol]}
        for symbol, count in ranked[:top_n]
    ]
    logger.debug(f"extracted {len(mentions)} distinct tickers, returning top {len(results)}")
    return results
