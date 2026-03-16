"""
Generate charts from historical crypto OHLC data.

Renders an ASCII line chart to the console and writes a Jupyter notebook with
candlestick, line, and OHLC charts to tmp/.

Output file: skills/check_crypto/tmp/chart_<COIN_ID>_<days>d_<timestamp>.ipynb

Usage:
    uv run skills/check_crypto/scripts/chart_history.py --input skills/check_crypto/tmp/history_bitcoin_365d_20260316_090000.json
    uv run skills/check_crypto/scripts/chart_history.py --input <path> --debug
"""

import argparse
import json
import sys
import time
from pathlib import Path

from check_crypto.charter import render_ascii_chart, write_notebook
from common.args import base_parser
from common.logger import setup

TMP_DIR = Path(__file__).parent.parent / "tmp"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate charts from historical crypto OHLC data",
        parents=[base_parser()],
    )
    parser.add_argument(
        "--input", required=True, help="Path to the history JSON file produced by fetch_history.py"
    )
    args = parser.parse_args()

    logger = setup(args.debug)
    input_path = Path(args.input)

    if not input_path.exists():
        logger.error(f"input file not found: {input_path}")
        sys.exit(1)

    history = json.loads(input_path.read_text())
    coin_id = history.get("coin_id", "unknown")
    days = history.get("days", 365)
    bars = history.get("bars", [])

    if not bars:
        logger.error(f"no bars found in {input_path}")
        sys.exit(1)

    logger.debug(f"charting {len(bars)} bars for {coin_id!r}")

    # ASCII chart to console
    render_ascii_chart(bars, coin_id)

    # Jupyter notebook
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    notebook_path = TMP_DIR / f"chart_{coin_id}_{days}d_{timestamp}.ipynb"
    try:
        write_notebook(bars, coin_id, str(notebook_path))
    except Exception as exc:
        logger.error(f"failed to write notebook: {exc}")
        sys.exit(1)

    logger.debug(f"wrote notebook to {notebook_path}")
    print(str(notebook_path))


if __name__ == "__main__":
    main()
