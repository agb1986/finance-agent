"""
Run the full daily finance pipeline: news → tickers → portfolios → trader → report → email.

Checkpointed per day — re-running resumes from the first incomplete stage.

Output: skills/daily_pipeline/tmp/run_<YYYYMMDD>/ (manifest.json, report.md, artifacts)

Usage:
    uv run skills/daily_pipeline/scripts/run_daily.py
    uv run skills/daily_pipeline/scripts/run_daily.py --dry-run
    uv run skills/daily_pipeline/scripts/run_daily.py --max-trader-runs 3 --skip-email
    uv run skills/daily_pipeline/scripts/run_daily.py --no-summary --debug
"""

import argparse
import sys
from pathlib import Path

from common.args import base_parser
from common.logger import setup
from daily_pipeline.config import load_config
from daily_pipeline.runner import StageError, plan, run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the full daily finance pipeline",
        parents=[base_parser()],
    )
    parser.add_argument("--config", type=Path, default=None, help="Alternative pipeline.yaml path")
    parser.add_argument("--date", default=None, help="Run date as YYYYMMDD (default: today)")
    parser.add_argument(
        "--dry-run", action="store_true", help="Print the plan without executing anything"
    )
    parser.add_argument(
        "--max-trader-runs", type=int, default=None, help="Override trader.max_runs"
    )
    parser.add_argument(
        "--skip-email", action="store_true", help="Build the report but do not send it"
    )
    parser.add_argument(
        "--no-summary", action="store_true", help="Skip the Claude executive summary"
    )
    args = parser.parse_args()

    logger = setup(args.debug)
    config = load_config(args.config)

    if args.dry_run:
        print("dry run — planned stages:")
        for step in plan(config):
            print(f"  - {step}")
        return

    try:
        manifest = run_pipeline(
            config,
            date=args.date,
            max_trader_runs=args.max_trader_runs,
            skip_email=args.skip_email,
            with_summary=not args.no_summary,
        )
    except StageError as exc:
        logger.error(f"pipeline failed: {exc}")
        sys.exit(1)

    print(manifest["report"])


if __name__ == "__main__":
    main()
