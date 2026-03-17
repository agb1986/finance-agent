"""Fetch Crypto.com portfolio (balance + positions) and print a human-readable summary.

Output file: skills/get_crypto_profilio/tmp/portfolio_<timestamp>.json

Usage:
    uv run skills/get_crypto_profilio/scripts/fetch_portfolio.py
    uv run skills/get_crypto_profilio/scripts/fetch_portfolio.py --debug

Environment:
    CRYPTO_API_KEY     Required. Your Crypto.com Exchange API key.
    CRYPTO_API_SECRET  Required. Your Crypto.com Exchange API secret.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

from common.args import base_parser
from common.logger import setup
from get_crypto_profilio.client import fetch_positions, fetch_user_balance, make_client
from get_crypto_profilio.formatter import format_portfolio

TMP_DIR = Path(__file__).parent.parent / "tmp"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch Crypto.com crypto portfolio summary",
        parents=[base_parser()],
    )
    args = parser.parse_args()

    logger = setup(args.debug)
    logger.debug("fetch_portfolio: starting")

    api_key = os.environ.get("CRYPTO_API_KEY")
    if not api_key:
        logger.error("CRYPTO_API_KEY environment variable not set")
        sys.exit(1)

    api_secret = os.environ.get("CRYPTO_API_SECRET")
    if not api_secret:
        logger.error("CRYPTO_API_SECRET environment variable not set")
        sys.exit(1)

    try:
        client = make_client()
        logger.debug("fetch_portfolio: fetching user balance")
        balances = fetch_user_balance(client, api_key, api_secret)
        logger.debug("fetch_portfolio: fetching open positions")
        positions = fetch_positions(client, api_key, api_secret)
    except Exception as exc:
        logger.error(f"failed to fetch portfolio: {exc}")
        sys.exit(1)

    fetched_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    portfolio = {
        "fetched_at": fetched_at,
        "balances": balances,
        "positions": positions,
    }

    TMP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_path = TMP_DIR / f"portfolio_{timestamp}.json"
    output_path.write_text(json.dumps(portfolio, indent=2))
    logger.debug(f"wrote portfolio to {output_path}")

    print(str(output_path))
    print()
    print(format_portfolio(balances, positions, fetched_at))


if __name__ == "__main__":
    main()
