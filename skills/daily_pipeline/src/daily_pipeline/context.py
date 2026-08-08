"""Build a compact market-data context for the trader panel.

The raw check_stock history JSON runs to tens of kilobytes; sent to all five
panel roles it would multiply prompt spend for little analytical gain. This
condenses quote + history into the numbers the analysts actually use: current
quote, period range, simple moving averages, and the most recent bars.
"""

from common.logger import get_logger

RECENT_BARS = 10
SMA_WINDOWS = (20, 50, 200)


def sma(closes: list[float], window: int) -> float | None:
    """Simple moving average over the last `window` closes, or None if too few."""
    if len(closes) < window:
        return None
    return round(sum(closes[-window:]) / window, 4)


def _fmt(value: object, suffix: str = "") -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:,.2f}{suffix}"
    if isinstance(value, int):
        return f"{value:,}{suffix}"
    return f"{value}{suffix}"


def build_context(quote: dict, history: dict) -> str:
    """Render quote + condensed history as plain text for the panel prompt."""
    logger = get_logger()
    symbol = quote.get("symbol", "?")
    bars = history.get("bars", [])
    closes = [bar["close"] for bar in bars]

    lines = [
        f"# {symbol} market data — fetched {quote.get('fetched_at', 'n/a')}",
        f"Name: {quote.get('name') or 'n/a'}",
        f"Price: {_fmt(quote.get('price'))} {quote.get('currency') or ''}".rstrip(),
        (
            f"Change vs previous close: {_fmt(quote.get('change'))} "
            f"({_fmt(quote.get('change_percent'), '%')})"
        ),
        f"Volume: {_fmt(quote.get('volume'))}",
        f"Market cap: {_fmt(quote.get('market_cap'))}",
        f"P/E ratio: {_fmt(quote.get('pe_ratio'))}",
        f"52-week range: {_fmt(quote.get('week_52_low'))} – {_fmt(quote.get('week_52_high'))}",
        "",
        f"## Price history ({history.get('period', '?')}, daily, {len(bars)} bars)",
    ]

    if bars:
        lines.append(
            f"Period range: low {_fmt(min(bar['low'] for bar in bars))} – "
            f"high {_fmt(max(bar['high'] for bar in bars))}"
        )
        sma_parts = [f"SMA{window}: {_fmt(sma(closes, window))}" for window in SMA_WINDOWS]
        lines.append("  ".join(sma_parts))
        lines.append("")
        lines.append(f"Last {min(RECENT_BARS, len(bars))} bars (oldest first):")
        lines.append("date | open | high | low | close | volume")
        for bar in bars[-RECENT_BARS:]:
            lines.append(
                f"{bar['date']} | {bar['open']} | {bar['high']} | {bar['low']} | "
                f"{bar['close']} | {bar['volume']}"
            )
    else:
        lines.append("No history bars available.")

    logger.debug(f"build_context: {symbol} context built from {len(bars)} bars")
    return "\n".join(lines)
