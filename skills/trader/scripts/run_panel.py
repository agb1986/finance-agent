"""
Run the analyst panel (Layer 1) for a stock symbol and write the briefs to a JSON file.

Output file: skills/trader/tmp/panel_<SYMBOL>_<timestamp>.json

Usage:
    uv run skills/trader/scripts/run_panel.py --symbol AMZN
    uv run skills/trader/scripts/run_panel.py --symbol AMZN --context-file path/to/quote.json
    uv run skills/trader/scripts/run_panel.py --symbol AMZN --debug
"""

import argparse
import json
import sys
import time
from pathlib import Path

from common.args import base_parser
from common.logger import setup
from trader.client import get_client
from trader.panel import run_panel
from trader.roles import load_config

TMP_DIR = Path(__file__).parent.parent / "tmp"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the analyst panel for a stock symbol",
        parents=[base_parser()],
    )
    parser.add_argument("--symbol", required=True, help="Ticker symbol, e.g. AMZN")
    parser.add_argument(
        "--context-file",
        default=None,
        help="Optional path to a JSON/text file with market data to ground the panel",
    )
    args = parser.parse_args()

    logger = setup(args.debug)
    symbol = args.symbol.upper()
    logger.debug(f"running panel: symbol={symbol!r}, context_file={args.context_file!r}")

    context = None
    if args.context_file:
        try:
            context = Path(args.context_file).read_text()
        except OSError as exc:
            logger.error(f"cannot read context file {args.context_file!r}: {exc}")
            sys.exit(1)

    try:
        client = get_client()
        config = load_config()
        panel, used = run_panel(client, config, symbol, context)
    except Exception as exc:
        logger.error(f"panel failed for {symbol!r}: {exc}")
        sys.exit(1)

    TMP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_path = TMP_DIR / f"panel_{symbol}_{timestamp}.json"
    output_path.write_text(
        json.dumps(
            {
                "symbol": symbol,
                "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "context_file": args.context_file,
                "panel": panel,
                # Carried forward by run_debate and run_judge so the final
                # verdict file holds the whole pipeline's token spend.
                "usage": used,
            },
            indent=2,
        )
    )

    logger.debug(f"wrote panel briefs for {symbol!r} to {output_path}")
    print(str(output_path))


if __name__ == "__main__":
    main()
