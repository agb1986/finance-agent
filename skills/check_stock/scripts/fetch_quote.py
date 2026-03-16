"""
Fetch the current quote for a stock symbol and write the result to a timestamped JSON file.

Output file: skills/check_stock/tmp/check_stock_<SYMBOL>_<timestamp>.json

Usage:
    uv run skills/check_stock/scripts/fetch_quote.py --symbol AMZN
    uv run skills/check_stock/scripts/fetch_quote.py --symbol AMZN --market NASDAQ
    uv run skills/check_stock/scripts/fetch_quote.py --symbol AMZN --debug
"""

import argparse
import json
import sys
import time
from pathlib import Path

from check_stock.fetcher import fetch_quote as fetch_quote_data
from common.args import base_parser
from common.logger import setup

TMP_DIR = Path(__file__).parent.parent / "tmp"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch the current quote for a stock symbol",
        parents=[base_parser()],
    )
    parser.add_argument("--symbol", required=True, help="Ticker symbol, e.g. AMZN")
    parser.add_argument("--market", default=None, help="Exchange/market, e.g. NASDAQ (optional)")
    args = parser.parse_args()

    logger = setup(args.debug)
    symbol = args.symbol.upper()
    logger.debug(f"checking stock: symbol={symbol!r}, market={args.market!r}")

    try:
        quote = fetch_quote_data(symbol, args.market)
    except NotImplementedError as exc:
        logger.error(str(exc))
        sys.exit(1)
    except Exception as exc:
        logger.error(f"failed to fetch quote for {symbol!r}: {exc}")
        sys.exit(1)

    TMP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_path = TMP_DIR / f"check_stock_{symbol}_{timestamp}.json"
    output_path.write_text(json.dumps(quote, indent=2))

    logger.debug(f"wrote quote for {symbol!r} to {output_path}")
    print(str(output_path))


if __name__ == "__main__":
    main()
