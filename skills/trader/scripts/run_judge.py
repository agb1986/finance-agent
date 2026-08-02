"""
Score a debate transcript with the judge (Layer 3) and write the verdict.

Output file: skills/trader/tmp/verdict_<SYMBOL>_<timestamp>.json

Usage:
    uv run skills/trader/scripts/run_judge.py --input skills/trader/tmp/debate_AMZN_x.json
    uv run skills/trader/scripts/run_judge.py --input <debate.json> --debug
"""

import argparse
import json
import sys
import time
from pathlib import Path

from common.args import base_parser
from common.logger import setup
from common.usage import merge
from trader.client import get_client
from trader.judge import run_judge
from trader.roles import load_config

TMP_DIR = Path(__file__).parent.parent / "tmp"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Score a debate transcript with the judge",
        parents=[base_parser()],
    )
    parser.add_argument("--input", required=True, help="Path to a debate_*.json file")
    args = parser.parse_args()

    logger = setup(args.debug)
    logger.debug(f"running judge: input={args.input!r}")

    try:
        data = json.loads(Path(args.input).read_text())
        symbol = data["symbol"]
        transcript = data["transcript"]
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        logger.error(f"cannot load debate file {args.input!r}: {exc}")
        sys.exit(1)

    try:
        client = get_client()
        config = load_config()
        verdict, used = run_judge(client, config, symbol, transcript)
    except Exception as exc:
        logger.error(f"judge failed for {symbol!r}: {exc}")
        sys.exit(1)

    # Final hop: panel + debate tokens plus this call, so the verdict file
    # carries the full cost of producing it.
    running = merge(data.get("usage"), used)

    TMP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_path = TMP_DIR / f"verdict_{symbol}_{timestamp}.json"
    output_path.write_text(
        json.dumps(
            {
                "symbol": symbol,
                "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "verdict": verdict,
                "usage": running,
            },
            indent=2,
        )
    )

    logger.debug(f"wrote verdict for {symbol!r} to {output_path}")
    print(str(output_path))


if __name__ == "__main__":
    main()
