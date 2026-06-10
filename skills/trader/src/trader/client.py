"""Thin wrapper around the Anthropic SDK for stateless, single-role calls."""

import os

from anthropic import Anthropic
from common.logger import get_logger


def get_client() -> Anthropic:
    """
    Return an Anthropic client, failing fast if no API key is configured.

    Raises:
        RuntimeError: If ANTHROPIC_API_KEY is not set in the environment.
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY is not set — export it before running trader")
    return Anthropic()


def call_role(
    client: Anthropic, model: str, system: str, user_message: str, max_tokens: int
) -> str:
    """
    Send one stateless message to a role and return the concatenated text response.

    Each call is independent — roles share no memory. "Switching" models between
    pipeline stages means re-packing accumulated context into the next call's
    user_message.

    Args:
        client: An Anthropic client (from get_client()).
        model: Model ID for this role, e.g. "claude-sonnet-4-6".
        system: The role's system prompt.
        user_message: The full context for this call.
        max_tokens: Response token cap for this role.

    Returns:
        The text content of the response.
    """
    logger = get_logger()
    logger.debug(
        f"call_role: model={model!r}, max_tokens={max_tokens}, prompt_chars={len(user_message)}"
    )

    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user_message}],
    )
    text = "".join(block.text for block in response.content if block.type == "text")

    logger.debug(f"call_role: {len(text)} chars returned by {model!r}")
    return text
