"""
Run the bull/bear debate (Layer 2) over a panel output file and write the transcript.

Output file: skills/trader/tmp/debate_<SYMBOL>_<timestamp>.json

Usage:
    uv run skills/trader/scripts/run_debate.py --input skills/trader/tmp/panel_AMZN_x.json
    uv run skills/trader/scripts/run_debate.py --input <panel.json> --rounds 3
    uv run skills/trader/scripts/run_debate.py --input <panel.json> --debug
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
from trader.debate import run_debate
from trader.roles import load_config

TMP_DIR = Path(__file__).parent.parent / "tmp"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the bull/bear debate over a panel output file",
        parents=[base_parser()],
    )
    parser.add_argument("--input", required=True, help="Path to a panel_*.json file")
    parser.add_argument("--rounds", type=int, default=2, help="Number of debate rounds (default 2)")
    args = parser.parse_args()

    logger = setup(args.debug)
    logger.debug(f"running debate: input={args.input!r}, rounds={args.rounds}")

    if args.rounds < 1:
        logger.error(f"--rounds must be >= 1, got {args.rounds}")
        sys.exit(1)

    try:
        data = json.loads(Path(args.input).read_text())
        symbol = data["symbol"]
        panel = data["panel"]
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        logger.error(f"cannot load panel file {args.input!r}: {exc}")
        sys.exit(1)

    try:
        client = get_client()
        config = load_config()
        transcript, used = run_debate(client, config, symbol, panel, args.rounds)
    except Exception as exc:
        logger.error(f"debate failed for {symbol!r}: {exc}")
        sys.exit(1)

    # Carry the panel's tokens forward — the verdict file is the only artifact
    # the daily pipeline reads, so the running total has to travel with it.
    running = merge(data.get("usage"), used)

    TMP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_path = TMP_DIR / f"debate_{symbol}_{timestamp}.json"
    output_path.write_text(
        json.dumps(
            {
                "symbol": symbol,
                "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "rounds": args.rounds,
                "panel": panel,
                "transcript": transcript,
                "usage": running,
            },
            indent=2,
        )
    )

    logger.debug(f"wrote debate transcript for {symbol!r} to {output_path}")
    print(str(output_path))


if __name__ == "__main__":
    main()
