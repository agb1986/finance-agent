"""
Crypto data fetching logic using the CoinGecko API.
"""

import datetime

from common.logger import get_logger
from pycoingecko import CoinGeckoAPI

logger = get_logger()


def fetch_quote(coin_id: str) -> dict:
    """Fetch the current quote for a cryptocurrency by CoinGecko coin ID.

    Args:
        coin_id: CoinGecko coin ID, e.g. 'bitcoin', 'ethereum'.

    Returns:
        A dict with price, market cap, 24h change, and related fields.

    Raises:
        ValueError: If the API returns no data for the given coin_id.
    """
    cg = CoinGeckoAPI()
    logger.debug(f"fetching quote for coin_id={coin_id!r}")

    data = cg.get_coin_by_id(
        coin_id,
        localization=False,
        tickers=False,
        market_data=True,
        community_data=False,
        developer_data=False,
        sparkline=False,
    )

    if not data:
        raise ValueError(f"no data returned for coin_id={coin_id!r}")

    md = data.get("market_data", {})

    quote = {
        "coin_id": data.get("id"),
        "symbol": (data.get("symbol") or "").upper(),
        "name": data.get("name"),
        "price": md.get("current_price", {}).get("usd"),
        "currency": "USD",
        "market_cap": md.get("market_cap", {}).get("usd"),
        "volume_24h": md.get("total_volume", {}).get("usd"),
        "change_24h": md.get("price_change_24h"),
        "change_percent_24h": md.get("price_change_percentage_24h"),
        "ath": md.get("ath", {}).get("usd"),
        "atl": md.get("atl", {}).get("usd"),
        "circulating_supply": md.get("circulating_supply"),
        "total_supply": md.get("total_supply"),
        "fetched_at": data.get("last_updated"),
    }

    logger.debug(f"fetched quote: {quote}")
    return quote


def fetch_history(coin_id: str, days: int = 365) -> dict:
    """Fetch historical daily OHLC data for a cryptocurrency.

    Args:
        coin_id: CoinGecko coin ID, e.g. 'bitcoin'.
        days: Number of days of history to fetch (default: 365).

    Returns:
        A dict with a 'bars' list of daily OHLC records.

    Raises:
        ValueError: If the API returns no data for the given coin_id.
    """
    cg = CoinGeckoAPI()
    logger.debug(f"fetching history for coin_id={coin_id!r}, days={days}")

    # OHLC endpoint returns [timestamp_ms, open, high, low, close]
    ohlc = cg.get_coin_ohlc_by_id(coin_id, vs_currency="usd", days=str(days))

    if not ohlc:
        raise ValueError(f"no OHLC data returned for coin_id={coin_id!r}")

    bars = []
    for row in ohlc:
        ts_ms, open_, high, low, close = row
        dt = datetime.datetime.fromtimestamp(ts_ms / 1000, tz=datetime.UTC)
        bars.append(
            {
                "date": dt.strftime("%Y-%m-%d"),
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
            }
        )

    logger.debug(f"fetched {len(bars)} OHLC bars for {coin_id!r}")
    return {
        "coin_id": coin_id,
        "days": days,
        "bars": bars,
    }
