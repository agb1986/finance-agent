"""
Send a Markdown report by email (SMTP with STARTTLS).

Usage:
    uv run skills/daily_pipeline/scripts/send_email.py --report path/to/report.md
    uv run skills/daily_pipeline/scripts/send_email.py --report report.md --subject "Custom"
    uv run skills/daily_pipeline/scripts/send_email.py --report report.md --debug

Environment (all required unless noted):
    SMTP_HOST, SMTP_USER, SMTP_PASSWORD, REPORT_TO
    SMTP_PORT (default 587), REPORT_FROM (default SMTP_USER)
"""

import argparse
import sys
import time
from pathlib import Path

from common.args import base_parser
from common.logger import setup
from daily_pipeline.emailer import send_report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Send a Markdown report by email",
        parents=[base_parser()],
    )
    parser.add_argument("--report", type=Path, required=True, help="Path to a Markdown report")
    parser.add_argument(
        "--subject",
        default=None,
        help="Email subject (default: 'Daily Finance Report — <date>')",
    )
    args = parser.parse_args()

    logger = setup(args.debug)

    try:
        body = args.report.read_text()
    except OSError as exc:
        logger.error(f"cannot read report {args.report}: {exc}")
        sys.exit(1)

    subject = args.subject or f"Daily Finance Report — {time.strftime('%Y-%m-%d')}"

    try:
        send_report(subject, body)
    except Exception as exc:
        logger.error(f"email delivery failed: {exc}")
        sys.exit(1)

    print(f"sent: {subject}")


if __name__ == "__main__":
    main()
