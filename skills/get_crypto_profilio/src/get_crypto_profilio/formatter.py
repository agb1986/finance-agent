"""Human-readable crypto portfolio formatter."""

from common.logger import get_logger

_GREEN = "\033[32m"
_RED = "\033[31m"
_RESET = "\033[0m"


def format_portfolio(balances: list[dict], positions: list[dict], fetched_at: str) -> str:
    """Format user balance and open positions into a human-readable report.

    Args:
        balances:   List of balance dicts from the Crypto.com user-balance API.
        positions:  List of position dicts from the Crypto.com get-positions API.
        fetched_at: ISO 8601 UTC timestamp string.

    Returns:
        A multi-line string ready to print to stdout.
    """
    logger = get_logger()
    logger.debug("format_portfolio: building crypto report")

    lines: list[str] = []
    lines.append(f"## Crypto.com Portfolio — {fetched_at[:10]}")
    lines.append("")

    # ── Account Balance ────────────────────────────────────────────────────────
    lines.append("### Account Balance")
    if balances:
        headers = [
            "Currency",
            "Cash Balance",
            "Margin Balance",
            "Available",
            "Unrealised PnL",
            "Realised PnL",
        ]
        col_w = [12, 16, 16, 16, 16, 14]
        header_row = "  " + "  ".join(h.ljust(w) for h, w in zip(headers, col_w))
        sep_row = "  " + "  ".join("-" * w for w in col_w)
        lines.append(header_row)
        lines.append(sep_row)

        for bal in balances:
            currency = bal.get("instrument_name", "?")
            cash = _fmt_float(bal.get("total_cash_balance", "0"))
            margin = _fmt_float(bal.get("total_margin_balance", "0"))
            available = _fmt_float(bal.get("total_available_balance", "0"))
            unrealised = _fmt_float(bal.get("total_session_unrealized_pnl", "0"))
            realised = _fmt_float(bal.get("total_session_realized_pnl", "0"))

            row = (
                f"  {currency:<{col_w[0]}}"
                f"  {cash:<{col_w[1]}}"
                f"  {margin:<{col_w[2]}}"
                f"  {available:<{col_w[3]}}"
                f"  {unrealised:<{col_w[4]}}"
                f"  {realised:<{col_w[5]}}"
            )
            lines.append(row)
    else:
        lines.append("  No balance data.")

    lines.append("")

    # ── Open Positions ─────────────────────────────────────────────────────────
    if positions:
        lines.append(f"### Open Positions ({len(positions)})")
        lines.append("")

        headers = ["Instrument", "Type", "Quantity", "Cost", "Unrealised PnL", "Realised PnL"]
        col_w = [22, 18, 14, 14, 16, 14]
        header_row = "  " + "  ".join(h.ljust(w) for h, w in zip(headers, col_w))
        sep_row = "  " + "  ".join("-" * w for w in col_w)
        lines.append(header_row)
        lines.append(sep_row)

        sorted_pos = sorted(
            positions,
            key=lambda p: float(p.get("cost") or 0),
            reverse=True,
        )

        for pos in sorted_pos:
            instrument = pos.get("instrument_name", "?")
            pos_type = pos.get("type", "?")
            quantity = _fmt_float(pos.get("quantity", "0"))
            cost = _fmt_float(pos.get("cost", "0"))
            unrealised = float(pos.get("open_position_pnl") or 0)
            realised = float(pos.get("cumulative_realized_pnl") or 0)
            unrealised_str = f"{_GREEN if unrealised >= 0 else _RED}{'+' if unrealised >= 0 else ''}{unrealised:.2f}{_RESET}"
            realised_str = f"{'+' if realised >= 0 else ''}{realised:.2f}"

            row = (
                f"  {instrument[: col_w[0]]:<{col_w[0]}}"
                f"  {pos_type[: col_w[1]]:<{col_w[1]}}"
                f"  {quantity:<{col_w[2]}}"
                f"  {cost:<{col_w[3]}}"
                f"  {unrealised_str}"
                f"  {realised_str}"
            )
            lines.append(row)
    else:
        lines.append("### Open Positions")
        lines.append("  No open positions.")

    logger.debug(f"format_portfolio: {len(positions)} positions formatted")
    return "\n".join(lines)


def _fmt_float(value: str | float | int) -> str:
    """Format a numeric value (possibly a string) to 2 decimal places."""
    try:
        return f"{float(value):,.2f}"
    except (ValueError, TypeError):
        return str(value)
