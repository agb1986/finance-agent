"""
Build the daily Markdown report from pipeline artifacts.

Output file: skills/daily_pipeline/tmp/report_<timestamp>.md

Usage:
    uv run skills/daily_pipeline/scripts/build_report.py --analysis a.json --tickers t.json
    uv run skills/daily_pipeline/scripts/build_report.py --analysis a.json --tickers t.json \
        --portfolio p.json --verdict v1.json --verdict v2.json
    uv run skills/daily_pipeline/scripts/build_report.py --analysis a.json --tickers t.json \
        --no-summary --debug
"""

import argparse
import time
from pathlib import Path

from common.args import base_parser
from common.logger import setup
from daily_pipeline.config import load_config
from daily_pipeline.report import build_report

TMP_DIR = Path(__file__).parent.parent / "tmp"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the daily Markdown report",
        parents=[base_parser()],
    )
    parser.add_argument("--analysis", type=Path, default=None, help="News analysis JSON")
    parser.add_argument("--tickers", type=Path, default=None, help="Extracted tickers JSON")
    parser.add_argument("--portfolio", type=Path, default=None, help="Stock portfolio JSON")
    parser.add_argument(
        "--verdict",
        type=Path,
        action="append",
        default=[],
        help="Trader verdict JSON (repeatable)",
    )
    parser.add_argument(
        "--no-summary", action="store_true", help="Skip the Claude executive summary"
    )
    args = parser.parse_args()

    logger = setup(args.debug)

    body = build_report(
        date=time.strftime("%Y-%m-%d"),
        analysis_path=str(args.analysis) if args.analysis else None,
        tickers_path=str(args.tickers) if args.tickers else None,
        portfolio_path=str(args.portfolio) if args.portfolio else None,
        verdicts=[{"path": str(v), "cached": False} for v in args.verdict],
        stages={},
        with_summary=not args.no_summary,
        pricing=load_config().get("pricing"),
    )

    TMP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_path = TMP_DIR / f"report_{timestamp}.md"
    output_path.write_text(body)

    logger.debug(f"wrote report to {output_path}")
    print(str(output_path))


if __name__ == "__main__":
    main()
