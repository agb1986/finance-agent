"""
Stock quote fetcher using yfinance.
"""

import time

import yfinance as yf
from common.logger import get_logger


def fetch_quote(symbol: str, market: str | None) -> dict:
    """
    Fetch the current quote for a stock symbol via yfinance.

    Args:
        symbol: Ticker symbol, e.g. "AMZN".
        market: Optional exchange/market, e.g. "NASDAQ". Currently unused by yfinance
                (symbol alone is sufficient for most markets) but recorded in output.

    Returns:
        {
            "symbol":         str,
            "market":         str | None,
            "fetched_at":     str,    # ISO 8601 UTC
            "name":           str | None,
            "price":          float | None,
            "currency":       str | None,
            "change":         float | None,   # absolute change vs. previous close
            "change_percent": float | None,   # percentage change vs. previous close
            "volume":         int | None,
            "market_cap":     int | None,
            "pe_ratio":       float | None,
            "week_52_high":   float | None,
            "week_52_low":    float | None,
        }

    Raises:
        ValueError: If yfinance returns no data for the symbol.
    """
    logger = get_logger()
    logger.debug(f"fetch_quote: symbol={symbol!r}, market={market!r}")

    ticker = yf.Ticker(symbol)
    info = ticker.info

    if not info or info.get("trailingPegRatio") is None and info.get("symbol") is None:
        # yfinance returns a near-empty dict for unknown symbols
        logger.debug(f"raw info keys returned: {list(info.keys())}")

    price = _coerce_float(info.get("currentPrice") or info.get("regularMarketPrice"))
    prev_close = _coerce_float(info.get("previousClose") or info.get("regularMarketPreviousClose"))

    change: float | None = None
    change_percent: float | None = None
    if price is not None and prev_close is not None and prev_close != 0:
        change = round(price - prev_close, 4)
        change_percent = round((change / prev_close) * 100, 4)

    fetched_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    quote = {
        "symbol": symbol,
        "market": market,
        "fetched_at": fetched_at,
        "name": info.get("longName") or info.get("shortName"),
        "price": price,
        "currency": info.get("currency"),
        "change": change,
        "change_percent": change_percent,
        "volume": _coerce_int(info.get("regularMarketVolume") or info.get("volume")),
        "market_cap": _coerce_int(info.get("marketCap")),
        "pe_ratio": _coerce_float(info.get("trailingPE")),
        "week_52_high": _coerce_float(info.get("fiftyTwoWeekHigh")),
        "week_52_low": _coerce_float(info.get("fiftyTwoWeekLow")),
    }

    logger.debug(f"quote fetched: price={quote['price']}, currency={quote['currency']}")
    return quote


VALID_PERIODS = {"1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"}
VALID_INTERVALS = {"1d", "5d", "1wk", "1mo", "3mo"}


def fetch_history(symbol: str, market: str | None, period: str = "1y") -> dict:
    """
    Fetch historical daily OHLCV data for a stock symbol via yfinance.

    Args:
        symbol: Ticker symbol, e.g. "AMZN".
        market: Optional exchange/market, recorded in output only.
        period: Lookback period. One of: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max.
                Defaults to "1y".

    Returns:
        {
            "symbol":     str,
            "market":     str | None,
            "period":     str,
            "fetched_at": str,   # ISO 8601 UTC
            "bars": [
                {
                    "date":   str,    # YYYY-MM-DD
                    "open":   float,
                    "high":   float,
                    "low":    float,
                    "close":  float,
                    "volume": int,
                },
                ...
            ]
        }

    Raises:
        ValueError: If the period is invalid or yfinance returns no data.
    """
    logger = get_logger()
    logger.debug(f"fetch_history: symbol={symbol!r}, market={market!r}, period={period!r}")

    if period not in VALID_PERIODS:
        raise ValueError(f"Invalid period {period!r}. Must be one of: {sorted(VALID_PERIODS)}")

    ticker = yf.Ticker(symbol)
    df = ticker.history(period=period, interval="1d")

    if df.empty:
        raise ValueError(f"No historical data returned for {symbol!r} with period={period!r}")

    bars = []
    for ts, row in df.iterrows():
        bars.append(
            {
                "date": ts.strftime("%Y-%m-%d"),
                "open": round(float(row["Open"]), 4),
                "high": round(float(row["High"]), 4),
                "low": round(float(row["Low"]), 4),
                "close": round(float(row["Close"]), 4),
                "volume": int(row["Volume"]),
            }
        )

    logger.debug(f"fetch_history: {len(bars)} bars returned for {symbol!r}")

    return {
        "symbol": symbol,
        "market": market,
        "period": period,
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "bars": bars,
    }


def _coerce_float(value: object) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _coerce_int(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
