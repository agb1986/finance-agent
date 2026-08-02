"""Token-usage accounting for Anthropic API calls.

Totals are keyed by model because cost estimation needs per-model rates — a
single flat token count can't be priced when a pipeline mixes Sonnet and Opus.

Every helper returns a new dict and never mutates its arguments, so the analyst
panel's concurrent per-role calls can each build their own totals and merge
afterwards without sharing state.
"""

FIELDS = (
    "input_tokens",
    "output_tokens",
    "cache_read_input_tokens",
    "cache_creation_input_tokens",
)

_KEYS = (*FIELDS, "calls")


def record(model: str, usage: object) -> dict:
    """Build a per-model usage dict from one response's ``usage`` object.

    Args:
        model: The model ID the call was made against.
        usage: The SDK's usage object (any object exposing the FIELDS as attributes).

    Returns:
        ``{model: {input_tokens, output_tokens, cache_*, calls}}`` for a single call.
    """
    counts = {field: _as_int(getattr(usage, field, 0)) for field in FIELDS}
    counts["calls"] = 1
    return {model: counts}


def merge(*totals: dict | None) -> dict:
    """Sum any number of per-model usage dicts into a new one."""
    merged: dict[str, dict[str, int]] = {}
    for total in totals:
        for model, counts in (total or {}).items():
            target = merged.setdefault(model, dict.fromkeys(_KEYS, 0))
            for key in _KEYS:
                target[key] += _as_int(counts.get(key, 0))
    return merged


def flatten(totals: dict | None) -> dict:
    """Collapse a per-model dict into overall counts across every model."""
    flat = dict.fromkeys(_KEYS, 0)
    for counts in (totals or {}).values():
        for key in _KEYS:
            flat[key] += _as_int(counts.get(key, 0))
    return flat


def _as_int(value: object) -> int:
    """Coerce a usage field to int. The SDK reports None for unset cache fields."""
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
