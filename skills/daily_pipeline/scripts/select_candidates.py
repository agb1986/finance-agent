"""
Select portfolio holdings that warrant a trader run.

Output file: skills/daily_pipeline/tmp/candidates_<timestamp>.json

Usage:
    uv run skills/daily_pipeline/scripts/select_candidates.py --input path/to/portfolio.json
    uv run skills/daily_pipeline/scripts/select_candidates.py --input portfolio.json --min-pnl-pct 5
    uv run skills/daily_pipeline/scripts/select_candidates.py --input portfolio.json --debug
"""

import argparse
import json
import sys
import time
from pathlib import Path

from common.args import base_parser
from common.logger import setup
from daily_pipeline.candidates import select_candidates

TMP_DIR = Path(__file__).parent.parent / "tmp"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Select portfolio holdings that warrant a trader run",
        parents=[base_parser()],
    )
    parser.add_argument(
        "--input", type=Path, required=True, help="Path to a Trading212 portfolio JSON"
    )
    parser.add_argument(
        "--min-pnl-pct", type=float, default=5.0, help="Minimum |unrealised P&L %%|"
    )
    parser.add_argument(
        "--min-value", type=float, default=25.0, help="Minimum current position value"
    )
    parser.add_argument("--max-candidates", type=int, default=3, help="Cap on candidates")
    args = parser.parse_args()

    logger = setup(args.debug)

    try:
        with args.input.open() as f:
            portfolio = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        logger.error(f"cannot load portfolio {args.input}: {exc}")
        sys.exit(1)

    results = select_candidates(portfolio, args.min_pnl_pct, args.min_value, args.max_candidates)

    TMP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_path = TMP_DIR / f"candidates_{timestamp}.json"
    output_path.write_text(json.dumps(results, indent=2))

    logger.debug(f"wrote {len(results)} candidates to {output_path}")
    print(str(output_path))


if __name__ == "__main__":
    main()
