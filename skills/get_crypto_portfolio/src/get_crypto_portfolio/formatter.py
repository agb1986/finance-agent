"""Human-readable crypto portfolio formatter."""

from common.logger import get_logger

_GREEN = "\033[32m"
_RED = "\033[31m"
_RESET = "\033[0m"


def format_portfolio(balances: list[dict], position_balances: list[dict], fetched_at: str) -> str:
    """Format user balance and open positions into a human-readable report.

    Args:
        balances:          List of balance dicts from the Crypto.com user-balance API.
        position_balances: Flattened list of position_balances dicts extracted from balances.
        fetched_at:        ISO 8601 UTC timestamp string.

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
    if position_balances:
        lines.append(f"### Open Positions ({len(position_balances)})")
        lines.append("")

        headers = ["Name", "Quantity", "Market Value", "Collateral Amount", "P/L"]
        col_w = [12, 18, 16, 18, 14]
        header_row = "  " + "  ".join(h.ljust(w) for h, w in zip(headers, col_w))
        sep_row = "  " + "  ".join("-" * w for w in col_w)
        lines.append(header_row)
        lines.append(sep_row)

        sorted_pos = sorted(
            position_balances,
            key=lambda p: float(p.get("market_value") or 0),
            reverse=True,
        )

        for pos in sorted_pos:
            name = pos.get("instrument_name", "?")
            quantity = _fmt_decimal(pos.get("quantity", "0"), decimals=7)
            market_value = float(pos.get("market_value") or 0)
            collateral = float(pos.get("collateral_amount") or 0)
            pnl = market_value - collateral
            pnl_str = f"{_GREEN if pnl >= 0 else _RED}{'+' if pnl >= 0 else ''}{pnl:.2f}{_RESET}"

            row = (
                f"  {name[: col_w[0]]:<{col_w[0]}}"
                f"  {quantity:<{col_w[1]}}"
                f"  {_fmt_float(market_value):<{col_w[2]}}"
                f"  {_fmt_float(collateral):<{col_w[3]}}"
                f"  {pnl_str}"
            )
            lines.append(row)
    else:
        lines.append("### Open Positions")
        lines.append("  No open positions.")

    logger.debug(f"format_portfolio: {len(position_balances)} positions formatted")
    return "\n".join(lines)


def _fmt_float(value: str | float | int) -> str:
    """Format a numeric value (possibly a string) to 2 decimal places."""
    try:
        return f"{float(value):,.2f}"
    except (ValueError, TypeError):
        return str(value)


def _fmt_decimal(value: str | float | int, decimals: int = 2) -> str:
    """Format a numeric value to a given number of decimal places, stripping trailing zeros."""
    try:
        return f"{float(value):.{decimals}f}".rstrip("0").rstrip(".")
    except (ValueError, TypeError):
        return str(value)
