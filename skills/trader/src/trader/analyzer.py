"""
Core trading analysis logic using the TradingAgents multi-agent framework.
"""

import os
import time
from pathlib import Path
from typing import Any

from common.logger import get_logger
from tradingagents.config import TradingAgentsConfig
from tradingagents.graph.trading_graph import TradingAgentsGraph

# Anthropic models used for the analyst agents
DEEP_THINK_MODEL = "claude-sonnet-4-6"
QUICK_THINK_MODEL = "claude-haiku-4-5-20251001"


def _build_config(results_dir: Path | None = None) -> TradingAgentsConfig:
    """Build the TradingAgents configuration for Anthropic/Claude.

    Args:
        results_dir: Directory for saving analysis results. Defaults to ./results.

    Returns:
        A TradingAgentsConfig configured to use Claude via Anthropic.
    """
    return TradingAgentsConfig(
        llm_provider="anthropic",
        deep_think_llm=DEEP_THINK_MODEL,
        quick_think_llm=QUICK_THINK_MODEL,
        max_debate_rounds=1,
        max_risk_discuss_rounds=1,
        max_recur_limit=25,
        reasoning_effort="medium",
        results_dir=results_dir or Path("./results"),
    )


def run_analysis(symbol: str, trade_date: str) -> dict[str, Any]:
    """
    Run a full TradingAgents pipeline for a stock symbol on a given date.

    Uses all four analyst agents (market, social, news, fundamentals) plus the
    bull/bear investment debate and risk assessment before a final trade decision.

    Args:
        symbol: Ticker symbol, e.g. "NVDA".
        trade_date: Analysis date in "YYYY-MM-DD" format.

    Returns:
        A dict containing:
        {
            "symbol":               str,
            "trade_date":           str,
            "analyzed_at":          str,   # ISO 8601 UTC
            "decision":             str,   # processed signal, e.g. "BUY" / "HOLD" / "SELL"
            "market_report":        str,
            "sentiment_report":     str,
            "news_report":          str,
            "fundamentals_report":  str,
            "investment_debate":    dict,  # bull/bear histories + judge decision
            "risk_debate":          dict,  # aggressive/conservative + judge
            "trader_plan":          str,
            "final_decision":       str,   # full text of the final trade decision
        }

    Raises:
        OSError: If ANTHROPIC_API_KEY is not set.
        RuntimeError: If the analysis pipeline fails.
    """
    logger = get_logger()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise OSError(
            "ANTHROPIC_API_KEY environment variable is not set. "
            "Export it before running: export ANTHROPIC_API_KEY=<your-key>"
        )

    logger.debug(f"run_analysis: symbol={symbol!r}, trade_date={trade_date!r}")

    config = _build_config()
    logger.debug(
        f"using llm_provider={config.llm_provider!r}, deep={config.deep_think_llm!r}"
    )

    ta = TradingAgentsGraph(
        selected_analysts=["market", "social", "news", "fundamentals"],
        debug=False,
        config=config,
    )

    logger.debug("propagating analysis pipeline…")
    try:
        final_state, decision = ta.propagate(symbol, trade_date)
    except Exception as exc:
        raise RuntimeError(f"TradingAgents pipeline failed for {symbol!r}: {exc}") from exc

    logger.debug(f"pipeline complete: decision={decision!r}")

    analyzed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    invest = final_state.investment_debate_state
    risk = final_state.risk_debate_state

    return {
        "symbol": symbol,
        "trade_date": trade_date,
        "analyzed_at": analyzed_at,
        "decision": decision or "",
        "market_report": final_state.market_report or "",
        "sentiment_report": final_state.sentiment_report or "",
        "news_report": final_state.news_report or "",
        "fundamentals_report": final_state.fundamentals_report or "",
        "investment_debate": {
            "bull_history": invest.bull_history or "",
            "bear_history": invest.bear_history or "",
            "judge_decision": invest.judge_decision or "",
        },
        "risk_debate": {
            "aggressive_history": risk.aggressive_history or "",
            "conservative_history": risk.conservative_history or "",
            "neutral_history": risk.neutral_history or "",
            "judge_decision": risk.judge_decision or "",
        },
        "trader_plan": final_state.trader_investment_plan or "",
        "final_decision": final_state.final_trade_decision or "",
    }


def render_report(result: dict[str, Any]) -> str:
    """
    Render a full markdown analysis report from a run_analysis result dict.

    Args:
        result: Dict returned by run_analysis().

    Returns:
        A markdown-formatted string suitable for saving to a .md file.
    """
    symbol = result["symbol"]
    trade_date = result["trade_date"]
    analyzed_at = result["analyzed_at"]
    decision = result.get("decision", "UNKNOWN").upper()

    investment_debate = result.get("investment_debate", {})
    risk_debate = result.get("risk_debate", {})

    bull_history = investment_debate.get("bull_history", "")
    bear_history = investment_debate.get("bear_history", "")
    invest_judge = investment_debate.get("judge_decision", "")

    risk_aggressive = risk_debate.get("aggressive_history", "")
    risk_conservative = risk_debate.get("conservative_history", "")
    risk_neutral = risk_debate.get("neutral_history", "")
    risk_judge = risk_debate.get("judge_decision", "")

    lines = [
        f"# Trading Analysis: {symbol} — {trade_date}",
        "",
        f"**Decision:** {decision}",
        f"**Analyzed at:** {analyzed_at}",
        "",
        "---",
        "",
    ]

    def _section(title: str, content: str) -> list[str]:
        if not content or not content.strip():
            return []
        return [f"## {title}", "", content.strip(), ""]

    lines += _section("Executive Summary", result.get("trader_plan", ""))
    lines += _section("Market Analysis", result.get("market_report", ""))
    lines += _section("Sentiment Analysis", result.get("sentiment_report", ""))
    lines += _section("News Analysis", result.get("news_report", ""))
    lines += _section("Fundamentals Analysis", result.get("fundamentals_report", ""))

    # Investment debate
    debate_parts: list[str] = []
    if bull_history:
        debate_parts += ["### Bull Case", "", str(bull_history).strip(), ""]
    if bear_history:
        debate_parts += ["### Bear Case", "", str(bear_history).strip(), ""]
    if invest_judge:
        debate_parts += ["### Judge Decision", "", str(invest_judge).strip(), ""]
    if debate_parts:
        lines += ["## Investment Debate", ""] + debate_parts

    # Risk debate
    risk_parts: list[str] = []
    if risk_aggressive:
        risk_parts += ["### Aggressive View", "", str(risk_aggressive).strip(), ""]
    if risk_conservative:
        risk_parts += ["### Conservative View", "", str(risk_conservative).strip(), ""]
    if risk_neutral:
        risk_parts += ["### Neutral View", "", str(risk_neutral).strip(), ""]
    if risk_judge:
        risk_parts += ["### Risk Judge Decision", "", str(risk_judge).strip(), ""]
    if risk_parts:
        lines += ["## Risk Assessment", ""] + risk_parts

    lines += _section("Final Trade Decision", result.get("final_decision", ""))

    lines += ["---", "", f"*Analysis generated at {analyzed_at}*", ""]

    return "\n".join(lines)
