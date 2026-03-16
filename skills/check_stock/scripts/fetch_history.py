"""
Fetch historical daily OHLCV data for a stock symbol and write the result to a timestamped JSON file.

Output file: skills/check_stock/tmp/history_<SYMBOL>_<period>_<timestamp>.json

Usage:
    uv run skills/check_stock/scripts/fetch_history.py --symbol AMZN
    uv run skills/check_stock/scripts/fetch_history.py --symbol AMZN --period 6mo
    uv run skills/check_stock/scripts/fetch_history.py --symbol AMZN --market NASDAQ --period 2y
    uv run skills/check_stock/scripts/fetch_history.py --symbol AMZN --debug
"""

import argparse
import json
import sys
import time
from pathlib import Path

from check_stock.fetcher import VALID_PERIODS
from check_stock.fetcher import fetch_history as fetch_history_data
from common.args import base_parser
from common.logger import setup

TMP_DIR = Path(__file__).parent.parent / "tmp"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch historical OHLCV data for a stock symbol",
        parents=[base_parser()],
    )
    parser.add_argument("--symbol", required=True, help="Ticker symbol, e.g. AMZN")
    parser.add_argument("--market", default=None, help="Exchange/market, e.g. NASDAQ (optional)")
    parser.add_argument(
        "--period",
        default="1y",
        choices=sorted(VALID_PERIODS),
        help="Lookback period (default: 1y)",
    )
    args = parser.parse_args()

    logger = setup(args.debug)
    symbol = args.symbol.upper()
    logger.debug(f"fetching history: symbol={symbol!r}, period={args.period!r}")

    try:
        history = fetch_history_data(symbol, args.market, args.period)
    except ValueError as exc:
        logger.error(str(exc))
        sys.exit(1)
    except Exception as exc:
        logger.error(f"failed to fetch history for {symbol!r}: {exc}")
        sys.exit(1)

    TMP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_path = TMP_DIR / f"history_{symbol}_{args.period}_{timestamp}.json"
    output_path.write_text(json.dumps(history, indent=2))

    logger.debug(f"wrote {len(history['bars'])} bars to {output_path}")
    print(str(output_path))


if __name__ == "__main__":
    main()
