"""Fetch Trading212 stock portfolio and print a human-readable summary.

Output file: skills/get_stock_portfolio/tmp/portfolio_<timestamp>.json

Usage:
    uv run skills/get_stock_portfolio/scripts/fetch_portfolio.py
    uv run skills/get_stock_portfolio/scripts/fetch_portfolio.py --debug

Environment:
    TRADING_212_API_KEY  Required. Your Trading212 API key.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

from common.args import base_parser
from common.logger import setup
from get_stock_portfolio.client import fetch_account_summary, fetch_positions, make_client
from get_stock_portfolio.formatter import format_portfolio

TMP_DIR = Path(__file__).parent.parent / "tmp"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch Trading212 stock portfolio summary",
        parents=[base_parser()],
    )
    args = parser.parse_args()

    logger = setup(args.debug)
    logger.debug("fetch_portfolio: starting")

    api_key = os.environ.get("TRADING_212_API_KEY")
    if not api_key:
        logger.error("TRADING_212_API_KEY environment variable not set")
        sys.exit(1)

    api_secret = os.environ.get("TRADING_212_API_SECRET")
    if not api_secret:
        logger.error("TRADING_212_API_SECRET environment variable not set")
        sys.exit(1)

    try:
        client = make_client(api_key, api_secret)
        logger.debug("fetch_portfolio: fetching account summary")
        summary = fetch_account_summary(client)
        logger.debug("fetch_portfolio: fetching open positions")
        positions = fetch_positions(client)
    except Exception as exc:
        logger.error(f"failed to fetch portfolio: {exc}")
        sys.exit(1)

    fetched_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    portfolio = {
        "fetched_at": fetched_at,
        "account_summary": summary,
        "positions": positions,
    }

    TMP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_path = TMP_DIR / f"portfolio_{timestamp}.json"
    output_path.write_text(json.dumps(portfolio, indent=2))
    logger.debug(f"wrote portfolio to {output_path}")

    print(str(output_path))
    print()
    print(format_portfolio(summary, positions, fetched_at))


if __name__ == "__main__":
    main()
