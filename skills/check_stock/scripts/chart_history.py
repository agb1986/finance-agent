"""
Generate charts from historical stock data and write a Jupyter notebook to the tmp directory.
Also renders an ASCII line chart to the console.

Output file: skills/check_stock/tmp/chart_<SYMBOL>_<period>_<timestamp>.ipynb

Usage:
    uv run skills/check_stock/scripts/chart_history.py --symbol AMZN
    uv run skills/check_stock/scripts/chart_history.py --input path/to/history.json
    uv run skills/check_stock/scripts/chart_history.py --debug
"""

import argparse
import json
import sys
import time
from pathlib import Path

from check_stock.charter import chart_to_console, chart_to_notebook, find_latest_history
from common.args import base_parser
from common.logger import setup

TMP_DIR = Path(__file__).parent.parent / "tmp"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate charts from historical stock data",
        parents=[base_parser()],
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="Path to a specific history JSON (default: most recent in tmp/)",
    )
    args = parser.parse_args()

    logger = setup(args.debug)

    try:
        input_path = args.input or find_latest_history(TMP_DIR)
    except FileNotFoundError as exc:
        logger.error(str(exc))
        sys.exit(1)

    logger.debug(f"reading history from {input_path}")

    try:
        data = json.loads(input_path.read_text())
    except Exception as exc:
        logger.error(f"failed to read {input_path}: {exc}")
        sys.exit(1)

    symbol = data.get("symbol", "UNKNOWN")
    period = data.get("period", "unknown")

    chart_to_console(data)

    TMP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_path = TMP_DIR / f"chart_{symbol}_{period}_{timestamp}.ipynb"

    try:
        chart_to_notebook(data, output_path)
    except Exception as exc:
        logger.error(f"failed to generate notebook: {exc}")
        sys.exit(1)

    logger.debug(f"notebook written to {output_path}")
    print(str(output_path))


if __name__ == "__main__":
    main()
