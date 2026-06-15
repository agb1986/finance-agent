"""Layer 1 — run the specialist analyst panel in parallel."""

from concurrent.futures import ThreadPoolExecutor

from anthropic import Anthropic
from common.logger import get_logger

from trader.client import call_role


def build_panel_prompt(symbol: str, context: str | None) -> str:
    """Build the shared prompt every panel role receives."""
    prompt = f"Analyse: {symbol}"
    if context:
        prompt += f"\n\nMARKET DATA:\n{context}"
    return prompt


def run_panel(
    client: Anthropic, config: dict, symbol: str, context: str | None = None
) -> dict[str, str]:
    """
    Run all panel roles in parallel on the same prompt.

    Args:
        client: An Anthropic client.
        config: The roles config (from trader.roles.load_config).
        symbol: Ticker symbol, e.g. "AMZN".
        context: Optional market data to ground the analysis.

    Returns:
        {role_name: brief} for every role in config["panel"].
    """
    logger = get_logger()
    prompt = build_panel_prompt(symbol, context)
    model = config["models"]["panel"]
    max_tokens = config["max_tokens"]["panel"]
    roles = config["panel"]
    logger.debug(f"run_panel: {len(roles)} roles on {model!r} for {symbol!r}")

    def _run(item: tuple[str, str]) -> tuple[str, str]:
        name, system = item
        return name, call_role(client, model, system, prompt, max_tokens)

    with ThreadPoolExecutor(max_workers=len(roles)) as pool:
        results = dict(pool.map(_run, roles.items()))

    logger.debug(f"run_panel: all {len(results)} briefs collected")
    return results
