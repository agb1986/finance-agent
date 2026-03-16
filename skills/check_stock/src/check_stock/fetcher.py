"""
Stock quote fetcher.

The fetch_quote function is a stub — implement it once an API provider has been chosen.
Expected return shape is documented below so the script and tests can be written against it.
"""

from common.logger import get_logger


def fetch_quote(symbol: str, market: str | None) -> dict:
    """
    Fetch the current quote for a stock symbol.

    Args:
        symbol: Ticker symbol, e.g. "AMZN".
        market: Optional exchange/market, e.g. "NASDAQ". May be used to disambiguate symbols.

    Returns:
        A dict with the following fields (unknown values set to None):
        {
            "symbol":         str,
            "market":         str | None,
            "fetched_at":     str,   # ISO 8601 UTC, e.g. "2026-03-16T09:00:00Z"
            "name":           str | None,  # full company name
            "price":          float | None,
            "currency":       str | None,  # e.g. "USD"
            "change":         float | None,  # absolute change vs. previous close
            "change_percent": float | None,  # percentage change vs. previous close
            "volume":         int | None,
            "market_cap":     int | None,
            "pe_ratio":       float | None,
            "week_52_high":   float | None,
            "week_52_low":    float | None,
        }

    Raises:
        NotImplementedError: Until an API provider is wired up.
    """
    logger = get_logger()
    logger.debug(f"fetch_quote called: symbol={symbol!r}, market={market!r}")
    raise NotImplementedError(
        "fetch_quote is not yet implemented. "
        "Choose an API provider (e.g. yfinance, Alpha Vantage, Polygon.io) and implement here."
    )
