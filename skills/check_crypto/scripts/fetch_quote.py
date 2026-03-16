"""
Fetch the current quote for a cryptocurrency and write the result to a timestamped JSON file.

Output file: skills/check_crypto/tmp/check_crypto_<COIN_ID>_<timestamp>.json

Usage:
    uv run skills/check_crypto/scripts/fetch_quote.py --coin bitcoin
    uv run skills/check_crypto/scripts/fetch_quote.py --coin ethereum --debug
"""

import argparse
import json
import sys
import time
from pathlib import Path

from check_crypto.fetcher import fetch_quote as fetch_quote_data
from common.args import base_parser
from common.logger import setup

TMP_DIR = Path(__file__).parent.parent / "tmp"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch the current quote for a cryptocurrency",
        parents=[base_parser()],
    )
    parser.add_argument("--coin", required=True, help="CoinGecko coin ID, e.g. bitcoin, ethereum")
    args = parser.parse_args()

    logger = setup(args.debug)
    coin_id = args.coin.lower()
    logger.debug(f"fetching crypto quote: coin_id={coin_id!r}")

    try:
        quote = fetch_quote_data(coin_id)
    except ValueError as exc:
        logger.error(str(exc))
        sys.exit(1)
    except Exception as exc:
        logger.error(f"failed to fetch quote for {coin_id!r}: {exc}")
        sys.exit(1)

    TMP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_path = TMP_DIR / f"check_crypto_{coin_id}_{timestamp}.json"
    output_path.write_text(json.dumps(quote, indent=2))

    logger.debug(f"wrote quote for {coin_id!r} to {output_path}")
    print(str(output_path))


if __name__ == "__main__":
    main()
