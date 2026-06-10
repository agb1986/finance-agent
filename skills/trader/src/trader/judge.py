"""Layer 3 — judge scores the full debate transcript against the rubric."""

import json
import re

from anthropic import Anthropic
from common.logger import get_logger

from trader.client import call_role


def format_transcript(transcript: list[dict]) -> str:
    """Render the debate transcript as text for the judge prompt."""
    return "\n\n".join(
        f"ROUND {entry['round']} — {entry['side'].upper()}:\n{entry['argument']}"
        for entry in transcript
    )


def parse_verdict(text: str) -> dict:
    """
    Parse the judge's JSON output, stripping markdown fences if present.

    On parse failure, return {"raw": <original text>, "parse_error": <reason>} so
    the pipeline still produces output the caller can inspect.
    """
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        get_logger().error(f"judge output is not valid JSON: {exc}")
        return {"raw": text, "parse_error": str(exc)}


def run_judge(client: Anthropic, config: dict, symbol: str, transcript: list[dict]) -> dict:
    """
    Score the debate transcript with the judge role.

    Args:
        client: An Anthropic client.
        config: The roles config.
        symbol: Ticker symbol.
        transcript: Debate transcript from run_debate.

    Returns:
        The parsed verdict dict (scorecard, winner, confidence, key fields), or a
        {"raw", "parse_error"} fallback if the judge returned malformed JSON.
    """
    logger = get_logger()
    model = config["models"]["judge"]
    logger.debug(f"run_judge: scoring {len(transcript)} transcript entries on {model!r}")

    prompt = f"Stock: {symbol}\n\nDEBATE TRANSCRIPT:\n{format_transcript(transcript)}"
    text = call_role(client, model, config["judge"], prompt, config["max_tokens"]["judge"])
    return parse_verdict(text)
