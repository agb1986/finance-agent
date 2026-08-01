"""Send the daily report by email (SMTP, HTML + plaintext alternative).

All connection settings come from the environment so no credentials ever live
in the repo or the config file:

    SMTP_HOST      Required. SMTP server hostname.
    SMTP_PORT      Optional. Defaults to 587 (STARTTLS).
    SMTP_USER      Required. Login user / from address default.
    SMTP_PASSWORD  Required. Login password (e.g. a Gmail app password).
    REPORT_TO      Required. Recipient address.
    REPORT_FROM    Optional. Defaults to SMTP_USER.
"""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import markdown as md
from common.logger import get_logger

REQUIRED_VARS = ["SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "REPORT_TO"]


def load_smtp_config() -> dict:
    """Read SMTP settings from the environment.

    Returns:
        Dict with host, port, user, password, to, from_addr.

    Raises:
        RuntimeError: If any required variable is missing, naming all of them.
    """
    missing = [var for var in REQUIRED_VARS if not os.environ.get(var)]
    if missing:
        raise RuntimeError(f"missing SMTP environment variables: {', '.join(missing)}")
    return {
        "host": os.environ["SMTP_HOST"],
        "port": int(os.environ.get("SMTP_PORT", "587")),
        "user": os.environ["SMTP_USER"],
        "password": os.environ["SMTP_PASSWORD"],
        "to": os.environ["REPORT_TO"],
        "from_addr": os.environ.get("REPORT_FROM") or os.environ["SMTP_USER"],
    }


def build_message(subject: str, markdown_body: str, from_addr: str, to_addr: str) -> MIMEMultipart:
    """Build a multipart/alternative message with plaintext and HTML parts."""
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = from_addr
    message["To"] = to_addr
    message.attach(MIMEText(markdown_body, "plain"))
    html = md.markdown(markdown_body, extensions=["tables"])
    message.attach(MIMEText(html, "html"))
    return message


def send_report(subject: str, markdown_body: str) -> None:
    """Send the report over SMTP with STARTTLS.

    Raises:
        RuntimeError: On missing configuration.
        smtplib.SMTPException / OSError: On delivery failure.
    """
    logger = get_logger()
    config = load_smtp_config()
    message = build_message(subject, markdown_body, config["from_addr"], config["to"])

    logger.debug(f"connecting to {config['host']}:{config['port']}")
    with smtplib.SMTP(config["host"], config["port"], timeout=30) as smtp:
        smtp.starttls()
        smtp.login(config["user"], config["password"])
        smtp.send_message(message)
    logger.debug(f"report sent to {config['to']}")
