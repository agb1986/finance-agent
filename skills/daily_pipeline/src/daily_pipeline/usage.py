"""Cost estimation and Markdown rendering for the report's token-usage section.

Token counts come from the artifacts (see common.usage); pricing lives in
pipeline.yaml so rates can be corrected without a code change when Anthropic
pricing shifts. A model with no configured rate still has its tokens reported —
it is named as unpriced rather than silently costed at zero.
"""

from collections.abc import Callable

from common.usage import flatten, merge

# Cache reads bill at roughly 0.1x the input rate and 5-minute cache writes at
# 1.25x. Nothing writes a cache today, but the arithmetic is here so the figure
# stays correct if prompt caching is added to the trader.
CACHE_READ_MULTIPLIER = 0.1
CACHE_WRITE_MULTIPLIER = 1.25

_PER_MILLION = 1_000_000


def estimate_cost(totals: dict | None, models: dict | None) -> tuple[float, list[str]]:
    """Estimate spend for a per-model usage dict.

    Args:
        totals: Per-model usage (see common.usage).
        models: ``{model: {"input": rate, "output": rate}}`` per million tokens.

    Returns:
        ``(cost, unpriced)`` — the estimate, and the sorted names of any models
        with no configured rate (their tokens are excluded from the cost).
    """
    models = models or {}
    cost = 0.0
    unpriced: list[str] = []
    for model, counts in (totals or {}).items():
        rates = models.get(model)
        if not rates:
            unpriced.append(model)
            continue
        rate_in = float(rates.get("input", 0.0))
        rate_out = float(rates.get("output", 0.0))
        cost += (
            counts.get("input_tokens", 0) * rate_in
            + counts.get("output_tokens", 0) * rate_out
            + counts.get("cache_read_input_tokens", 0) * rate_in * CACHE_READ_MULTIPLIER
            + counts.get("cache_creation_input_tokens", 0) * rate_in * CACHE_WRITE_MULTIPLIER
        ) / _PER_MILLION
    return cost, sorted(unpriced)


def format_money(value: float, currency: str = "$") -> str:
    """Format a cost, keeping sub-cent estimates from rounding away to zero."""
    if 0 < value < 0.01:
        return f"{currency}{value:.4f}"
    return f"{currency}{value:,.2f}"


def format_usage_section(
    spent: dict | None, reused: dict | None, pricing: dict | None = None
) -> str:
    """Render token usage as a Markdown table.

    Args:
        spent:   Per-model usage actually charged during this run.
        reused:  Per-model usage attached to cached verdicts — real tokens, but
                 billed on an earlier day, so they are reported separately
                 rather than inflating today's total.
        pricing: The ``pricing`` config block (currency + per-model rates).

    Returns:
        A Markdown section body.
    """
    pricing = pricing or {}
    currency = pricing.get("currency", "$")
    models = pricing.get("models", {})

    if not spent and not reused:
        return "_No Anthropic API calls were made for this report._"

    lines: list[str] = []
    if spent:
        lines.extend(["| Model | Calls | Input | Output | Cost |", "|---|---|---|---|---|"])
        for model in sorted(spent):
            counts = spent[model]
            cost, _ = estimate_cost({model: counts}, models)
            priced = model in models
            lines.append(
                f"| {model} "
                f"| {counts.get('calls', 0):,} "
                f"| {counts.get('input_tokens', 0):,} "
                f"| {counts.get('output_tokens', 0):,} "
                f"| {format_money(cost, currency) if priced else '—'} |"
            )
        overall = flatten(spent)
        total_cost, unpriced = estimate_cost(spent, models)
        lines.append(
            f"| **Total** "
            f"| **{overall['calls']:,}** "
            f"| **{overall['input_tokens']:,}** "
            f"| **{overall['output_tokens']:,}** "
            f"| **{format_money(total_cost, currency)}** |"
        )
        if unpriced:
            lines.extend(
                [
                    "",
                    f"_No configured price for {', '.join(unpriced)} — "
                    f"their tokens are counted above but excluded from the cost._",
                ]
            )
    else:
        lines.append("_No API calls were charged today — every verdict came from cache._")

    if reused:
        cached = flatten(reused)
        cached_cost, _ = estimate_cost(reused, models)
        saved = f", ~{format_money(cached_cost, currency)} saved" if cached_cost else ""
        lines.extend(
            [
                "",
                f"_Reused {cached['calls']:,} cached API "
                f"{'call' if cached['calls'] == 1 else 'calls'} "
                f"({cached['input_tokens'] + cached['output_tokens']:,} tokens{saved}) — "
                f"charged on an earlier run, not today._",
            ]
        )
    return "\n".join(lines)


def split_verdict_usage(verdicts: list[dict], load: Callable) -> tuple[dict, dict]:
    """Split verdict-file token usage into charged-today and reused-from-cache.

    Args:
        verdicts: ``{"path", "cached"}`` entries as passed to build_report.
        load:     Callable that reads a JSON path (injected so the caller owns I/O).

    Returns:
        ``(spent, reused)`` per-model usage dicts.
    """
    spent: dict = {}
    reused: dict = {}
    for entry in verdicts:
        try:
            data = load(entry["path"])
        except (OSError, ValueError):
            continue
        used = data.get("usage") if isinstance(data, dict) else None
        if not used:
            continue
        if entry.get("cached"):
            reused = merge(reused, used)
        else:
            spent = merge(spent, used)
    return spent, reused


__all__ = [
    "estimate_cost",
    "format_money",
    "format_usage_section",
    "split_verdict_usage",
]
