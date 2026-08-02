"""Thin wrapper around the Anthropic SDK for stateless, single-role calls."""

import os
import subprocess

from anthropic import Anthropic
from common.logger import get_logger
from common.usage import record


def get_client() -> Anthropic:
    """
    Return an Anthropic client, failing fast if no API key is configured.

    Falls back to secret-tool if ANTHROPIC_API_KEY is not in the environment.

    Raises:
        RuntimeError: If ANTHROPIC_API_KEY cannot be found via env or secret-tool.
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        try:
            result = subprocess.run(
                ["secret-tool", "lookup", "service", "anthropic", "key", "api-key"],
                capture_output=True,
                text=True,
                check=True,
            )
            os.environ["ANTHROPIC_API_KEY"] = result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set and secret-tool lookup failed — "
                "export it or store it with: "
                "secret-tool store --label='Anthropic API Key' service anthropic key api-key"
            )
    return Anthropic()


def call_role(
    client: Anthropic, model: str, system: str, user_message: str, max_tokens: int
) -> tuple[str, dict]:
    """
    Send one stateless message to a role and return its text plus token usage.

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
        ``(text, usage)`` — the response text and a per-model usage dict
        (see common.usage) so callers can report token spend.
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
    used = record(model, getattr(response, "usage", None))

    logger.debug(
        f"call_role: {len(text)} chars returned by {model!r} "
        f"({used[model]['input_tokens']} in / {used[model]['output_tokens']} out)"
    )
    return text, used
