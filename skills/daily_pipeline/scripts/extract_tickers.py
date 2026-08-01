"""
Extract the top ticker mentions from a news analysis JSON file.

Output file: skills/daily_pipeline/tmp/tickers_<timestamp>.json

Usage:
    uv run skills/daily_pipeline/scripts/extract_tickers.py --input path/to/analysis.json
    uv run skills/daily_pipeline/scripts/extract_tickers.py --input analysis.json --top-n 5
    uv run skills/daily_pipeline/scripts/extract_tickers.py --input analysis.json --debug
"""

import argparse
import json
import sys
import time
from pathlib import Path

from common.args import base_parser
from common.logger import setup
from daily_pipeline.tickers import extract_tickers, load_ticker_map

TMP_DIR = Path(__file__).parent.parent / "tmp"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract top ticker mentions from analysed news",
        parents=[base_parser()],
    )
    parser.add_argument("--input", type=Path, required=True, help="Path to an analysis JSON file")
    parser.add_argument("--top-n", type=int, default=5, help="Number of tickers to return")
    parser.add_argument("--map", type=Path, default=None, help="Alternative ticker_map.json path")
    args = parser.parse_args()

    logger = setup(args.debug)

    try:
        with args.input.open() as f:
            articles = json.load(f)
        ticker_map = load_ticker_map(args.map)
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        logger.error(f"cannot load inputs: {exc}")
        sys.exit(1)

    results = extract_tickers(articles, ticker_map, args.top_n)

    TMP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_path = TMP_DIR / f"tickers_{timestamp}.json"
    output_path.write_text(json.dumps(results, indent=2))

    logger.debug(f"wrote {len(results)} tickers to {output_path}")
    print(str(output_path))


if __name__ == "__main__":
    main()
