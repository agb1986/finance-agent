"""Layer 2 — bull/bear debate over the panel output, fixed rounds."""

from anthropic import Anthropic
from common.logger import get_logger
from common.usage import merge

from trader.client import call_role


def build_base_prompt(symbol: str, panel: dict[str, str]) -> str:
    """Build the shared debate context — both advocates argue from the same facts."""
    summary = "\n\n".join(f"{name.upper()}:\n{brief}" for name, brief in panel.items())
    return f"Stock: {symbol}\n\nPANEL:\n{summary}"


def run_debate(
    client: Anthropic, config: dict, symbol: str, panel: dict[str, str], rounds: int = 2
) -> tuple[list[dict], dict]:
    """
    Run a fixed-rounds bull/bear debate.

    Round 1 is argued independently from the panel data only; each later round
    rebuts the opponent's argument from the previous round.

    Args:
        client: An Anthropic client.
        config: The roles config.
        symbol: Ticker symbol.
        panel: {role_name: brief} from run_panel.
        rounds: Number of rounds (default 2 — marginal value drops sharply after).

    Returns:
        ``(transcript, usage)`` — the transcript as a list of
        {"round": int, "side": "bull"|"bear", "argument": str}, plus the
        combined token usage across every round.
    """
    logger = get_logger()
    base = build_base_prompt(symbol, panel)
    model = config["models"]["debate"]
    max_tokens = config["max_tokens"]["debate"]
    systems = {"bull": config["debate"]["bull"], "bear": config["debate"]["bear"]}

    transcript: list[dict] = []
    total: dict = {}
    prev: dict[str, str | None] = {"bull": None, "bear": None}

    for round_no in range(1, rounds + 1):
        logger.debug(f"run_debate: round {round_no} on {model!r}")
        prompts = {
            "bull": base if prev["bear"] is None else f"{base}\n\nBEAR TO REBUT:\n{prev['bear']}",
            "bear": base if prev["bull"] is None else f"{base}\n\nBULL TO REBUT:\n{prev['bull']}",
        }
        current: dict[str, str] = {}
        for side in ("bull", "bear"):
            text, used = call_role(client, model, systems[side], prompts[side], max_tokens)
            current[side] = text
            total = merge(total, used)
        for side in ("bull", "bear"):
            transcript.append({"round": round_no, "side": side, "argument": current[side]})
        prev = dict(current)

    logger.debug(f"run_debate: transcript has {len(transcript)} entries")
    return transcript, total
