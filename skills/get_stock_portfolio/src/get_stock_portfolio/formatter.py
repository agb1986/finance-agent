"""Human-readable portfolio formatter."""

from datetime import datetime

from common.logger import get_logger

_GREEN = "\033[32m"
_RED = "\033[31m"
_RESET = "\033[0m"


def _fmt_date(iso: str) -> str:
    """Parse an ISO 8601 datetime string and return DD/MM/YYYY."""
    try:
        # Strip timezone offset so fromisoformat handles it on Python 3.10
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return iso


def format_portfolio(summary: dict, positions: list[dict], fetched_at: str) -> str:
    """Format account summary and open positions into a human-readable report.

    Args:
        summary:    Raw account summary dict from the Trading212 API.
        positions:  Raw list of open position dicts from the Trading212 API.
        fetched_at: ISO 8601 UTC timestamp string.

    Returns:
        A multi-line string ready to print to stdout.
    """
    logger = get_logger()
    logger.debug("format_portfolio: building report")

    lines: list[str] = []

    investments = summary.get("investments", {}) or {}
    total_value = float(summary.get("totalValue") or 0.0)
    invested = float(investments.get("totalCost") or 0.0)
    unrealised = float(investments.get("unrealizedProfitLoss") or 0.0)
    realised = float(investments.get("realizedProfitLoss") or 0.0)
    currency = summary.get("currency", "")

    unrealised_sign = "+" if unrealised >= 0 else ""
    realised_sign = "+" if realised >= 0 else ""

    lines.append(f"## Trading212 Portfolio — {fetched_at[:10]}")
    lines.append("")
    lines.append("### Account Summary")
    lines.append(f"  Currency:       {currency}")
    lines.append(f"  Total Value:    {total_value:,.2f}")
    lines.append(f"  Invested:       {invested:,.2f}")
    lines.append(f"  Unrealised P&L: {unrealised_sign}{unrealised:,.2f}")
    lines.append(f"  Realised P&L:   {realised_sign}{realised:,.2f}")
    lines.append("")

    if positions:
        lines.append(f"### Open Positions ({len(positions)})")
        lines.append("")

        headers = [
            "Name",
            "ISIN",
            "Date Bought",
            "Shares",
            "Price",
            "Total Cost",
            "Current Value",
            "P&L",
        ]
        col_w = [30, 14, 12, 10, 10, 13, 15, 14]

        header_row = "  " + "  ".join(h.ljust(w) for h, w in zip(headers, col_w))
        sep_row = "  " + "  ".join("-" * w for w in col_w)
        lines.append(header_row)
        lines.append(sep_row)

        sorted_pos = sorted(
            positions,
            key=lambda p: float((p.get("walletImpact") or {}).get("currentValue") or 0),
            reverse=True,
        )

        for pos in sorted_pos:
            instrument = pos.get("instrument", {}) or {}
            wallet = pos.get("walletImpact", {}) or {}

            name = instrument.get("name", "?")
            isin = instrument.get("isin", "?")
            date_bought = _fmt_date(pos.get("createdAt", ""))
            qty = float(pos.get("quantity") or 0)
            curr_price = float(pos.get("currentPrice") or 0)
            total_cost = float(wallet.get("totalCost") or 0)
            curr_value = float(wallet.get("currentValue") or 0)
            pnl = curr_value - total_cost
            pnl_sign = "+" if pnl >= 0 else ""

            row = (
                f"  {name[: col_w[0]]:<{col_w[0]}}"
                f"  {isin:<{col_w[1]}}"
                f"  {date_bought:<{col_w[2]}}"
                f"  {qty:<{col_w[3]}.4f}"
                f"  {curr_price:<{col_w[4]}.2f}"
                f"  {total_cost:<{col_w[5]}.2f}"
                f"  {curr_value:<{col_w[6]}.2f}"
                f"  {_GREEN if pnl >= 0 else _RED}{pnl_sign}{pnl:.2f}{_RESET}"
            )
            lines.append(row)
    else:
        lines.append("### Open Positions")
        lines.append("  No open positions.")

    logger.debug(f"format_portfolio: {len(positions)} positions formatted")
    return "\n".join(lines)
