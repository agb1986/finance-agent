"""
Run a full TradingAgents analysis for a stock and save a markdown report to tmp/.

Output file: skills/trader/tmp/trader_<SYMBOL>_<DATE>_<timestamp>.md

Usage:
    uv run skills/trader/scripts/analyze_stock.py --symbol NVDA
    uv run skills/trader/scripts/analyze_stock.py --symbol NVDA --date 2026-01-15
    uv run skills/trader/scripts/analyze_stock.py --symbol NVDA --debug
"""

import argparse
import sys
import time
from pathlib import Path

from common.args import base_parser
from common.logger import setup
from trader.analyzer import render_report, run_analysis

TMP_DIR = Path(__file__).parent.parent / "tmp"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a TradingAgents stock analysis and save a markdown report",
        parents=[base_parser()],
    )
    parser.add_argument("--symbol", required=True, help="Ticker symbol, e.g. NVDA")
    parser.add_argument(
        "--date",
        default=None,
        help="Analysis date in YYYY-MM-DD format (default: today)",
    )
    args = parser.parse_args()

    logger = setup(args.debug)
    symbol = args.symbol.upper()
    trade_date = args.date or time.strftime("%Y-%m-%d", time.gmtime())

    logger.debug(f"analyze_stock: symbol={symbol!r}, trade_date={trade_date!r}")

    try:
        result = run_analysis(symbol, trade_date)
    except OSError as exc:
        logger.error(str(exc))
        sys.exit(1)
    except RuntimeError as exc:
        logger.error(str(exc))
        sys.exit(1)
    except Exception as exc:
        logger.error(f"unexpected error during analysis of {symbol!r}: {exc}")
        sys.exit(1)

    report = render_report(result)

    TMP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_path = TMP_DIR / f"trader_{symbol}_{trade_date}_{timestamp}.md"
    output_path.write_text(report, encoding="utf-8")

    logger.debug(f"wrote report for {symbol!r} to {output_path}")
    print(str(output_path))


if __name__ == "__main__":
    main()
