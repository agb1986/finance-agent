"""
Fetch historical OHLC data for a cryptocurrency and write the result to a timestamped JSON file.

Output file: skills/check_crypto/tmp/history_<COIN_ID>_<days>d_<timestamp>.json

Usage:
    uv run skills/check_crypto/scripts/fetch_history.py --coin bitcoin
    uv run skills/check_crypto/scripts/fetch_history.py --coin ethereum --days 90
    uv run skills/check_crypto/scripts/fetch_history.py --coin bitcoin --debug
"""

import argparse
import json
import sys
import time
from pathlib import Path

from check_crypto.fetcher import fetch_history as fetch_history_data
from common.args import base_parser
from common.logger import setup

TMP_DIR = Path(__file__).parent.parent / "tmp"

VALID_DAYS = [1, 7, 14, 30, 90, 180, 365]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch historical OHLC data for a cryptocurrency",
        parents=[base_parser()],
    )
    parser.add_argument("--coin", required=True, help="CoinGecko coin ID, e.g. bitcoin, ethereum")
    parser.add_argument(
        "--days",
        type=int,
        default=365,
        help=f"Days of history to fetch. One of: {VALID_DAYS} (default: 365)",
    )
    args = parser.parse_args()

    logger = setup(args.debug)
    coin_id = args.coin.lower()
    logger.debug(f"fetching crypto history: coin_id={coin_id!r}, days={args.days}")

    try:
        history = fetch_history_data(coin_id, args.days)
    except ValueError as exc:
        logger.error(str(exc))
        sys.exit(1)
    except Exception as exc:
        logger.error(f"failed to fetch history for {coin_id!r}: {exc}")
        sys.exit(1)

    TMP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_path = TMP_DIR / f"history_{coin_id}_{args.days}d_{timestamp}.json"
    output_path.write_text(json.dumps(history, indent=2))

    logger.debug(f"wrote history for {coin_id!r} to {output_path}")
    print(str(output_path))


if __name__ == "__main__":
    main()
