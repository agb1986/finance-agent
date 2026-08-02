"""Select portfolio holdings that warrant a trader run.

Works on the Trading212 portfolio JSON produced by
skills/get_stock_portfolio/scripts/fetch_portfolio.py. A holding qualifies when
its unrealised P&L swing exceeds the configured threshold and the position is
large enough to matter.
"""

from common.logger import get_logger


def symbol_from_instrument(ticker: str) -> str:
    """Extract the plain symbol from a Trading212 instrument ticker.

    Trading212 tickers look like ``AMZN_US_EQ`` — the symbol is the first
    underscore-separated segment.
    """
    return ticker.split("_")[0].upper()


def select_candidates(
    portfolio: dict,
    min_abs_pnl_pct: float = 5.0,
    min_position_value: float = 25.0,
    max_candidates: int = 3,
) -> list[dict]:
    """Return holdings whose P&L swing crosses the review threshold.

    Args:
        portfolio:          Parsed portfolio JSON (``positions`` list expected).
        min_abs_pnl_pct:    Minimum |unrealised P&L %| to qualify.
        min_position_value: Minimum current position value to qualify.
        max_candidates:     Cap on returned candidates.

    Returns:
        List of ``{"symbol", "name", "pnl_pct", "current_value"}`` dicts sorted
        by |P&L %| descending.
    """
    logger = get_logger()
    candidates: list[dict] = []

    for position in portfolio.get("positions", []):
        instrument = position.get("instrument", {})
        wallet = position.get("walletImpact", {})
        total_cost = wallet.get("totalCost") or 0
        current_value = wallet.get("currentValue") or 0
        unrealised = wallet.get("unrealizedProfitLoss") or 0

        if total_cost <= 0:
            logger.debug(f"skipping {instrument.get('ticker')!r}: no cost basis")
            continue

        pnl_pct = unrealised / total_cost * 100
        if current_value < min_position_value:
            logger.debug(f"skipping {instrument.get('ticker')!r}: value {current_value} too small")
            continue
        if abs(pnl_pct) < min_abs_pnl_pct:
            logger.debug(f"skipping {instrument.get('ticker')!r}: |pnl| {pnl_pct:.2f}% below bar")
            continue

        candidates.append(
            {
                "symbol": symbol_from_instrument(instrument.get("ticker", "")),
                "name": instrument.get("name", ""),
                "pnl_pct": round(pnl_pct, 2),
                "current_value": current_value,
            }
        )

    candidates.sort(key=lambda c: -abs(c["pnl_pct"]))
    selected = candidates[:max_candidates]
    logger.debug(f"selected {len(selected)} of {len(candidates)} qualifying holdings")
    return selected
