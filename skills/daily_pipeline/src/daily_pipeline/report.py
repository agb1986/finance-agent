"""Assemble the daily Markdown report from pipeline artifacts.

Everything except the executive summary is deterministic templating over the
JSON artifacts the other stages produced. The summary is a single Claude call
and is skipped gracefully when no API key is available.
"""

import json
import os
from pathlib import Path

from common.logger import get_logger

from common import usage as usage_lib
from daily_pipeline import usage as usage_report

SUMMARY_MODEL = "claude-opus-5"
SUMMARY_MAX_TOKENS = 2000

# Placeholder swapped for the rendered usage table once the summary call is done.
_USAGE_MARKER = "<!-- token-usage -->"

_SCORE_DIMENSIONS = [
    ("Evidence quality", "evidence_quality"),
    ("Rebuttal validity", "rebuttal_validity"),
    ("Risk-adjusted logic", "risk_adjusted_logic"),
    ("Internal consistency", "internal_consistency"),
    ("Falsifiability", "falsifiability"),
]


def _load_json(path: str | Path) -> dict | list:
    with Path(path).open() as f:
        return json.load(f)


def format_news_section(articles: list[dict], top_n: int = 5) -> str:
    """Render the top-ranked articles as Markdown."""
    if not articles:
        return "_No articles matched the analysis thresholds._"
    lines: list[str] = []
    for article in articles[:top_n]:
        keywords = ", ".join(f"`{k}`" for k in article.get("matched_keywords", []))
        score_line = (
            f"*{article.get('source', '?')}* · "
            f"semantic: {article.get('semantic_score', 0):.2f} · "
            f"keyword: {article.get('keyword_score', 0):.2f}"
        )
        if keywords:
            score_line += f" ({keywords})"
        lines.append(f"**#{article.get('rank', '?')} — {article.get('title', 'Untitled')}**")
        lines.append(score_line)
        if article.get("summary"):
            lines.append(f"> {article['summary']}")
        lines.append(f"> [Read more]({article.get('url', '')})")
        lines.append("")
    return "\n".join(lines).rstrip()


def format_tickers_section(tickers: list[dict]) -> str:
    """Render the top ticker mentions as a Markdown table."""
    if not tickers:
        return "_No known tickers were mentioned in today's articles._"
    lines = ["| Symbol | Mentions |", "|---|---|"]
    lines.extend(f"| {t['symbol']} | {t['mentions']} |" for t in tickers)
    return "\n".join(lines)


def format_portfolio_section(portfolio: dict | None) -> str:
    """Render the Trading212 account summary and positions as Markdown."""
    if not portfolio:
        return "_Portfolio fetch was skipped or failed (missing credentials?)._"
    summary = portfolio.get("account_summary", {})
    investments = summary.get("investments", {})
    lines = [
        f"**Currency:** {summary.get('currency', '?')}",
        f"**Total Value:** {summary.get('totalValue', 0):.2f}",
        f"**Invested:** {investments.get('totalCost', 0):.2f}",
        f"**Unrealised P&L:** {investments.get('unrealizedProfitLoss', 0):+.2f}",
        "",
    ]
    positions = portfolio.get("positions", [])
    if positions:
        lines.append("| Name | Shares | Price | Value | P&L |")
        lines.append("|---|---|---|---|---|")
        for position in positions:
            instrument = position.get("instrument", {})
            wallet = position.get("walletImpact", {})
            pnl = (wallet.get("currentValue") or 0) - (wallet.get("totalCost") or 0)
            lines.append(
                f"| {instrument.get('name', '?')} "
                f"| {position.get('quantity', 0):.4f} "
                f"| {position.get('currentPrice', 0):.2f} "
                f"| {wallet.get('currentValue', 0):.2f} "
                f"| {pnl:+.2f} |"
            )
    return "\n".join(lines)


def format_crypto_section(portfolio: dict | None) -> str:
    """Render the Crypto.com balance and positions as Markdown."""
    if not portfolio:
        return "_Crypto portfolio fetch was skipped or failed (missing credentials?)._"
    lines: list[str] = []
    for balance in portfolio.get("balances", []):
        lines.extend(
            [
                f"**Currency:** {balance.get('instrument_name', '?')}",
                f"**Cash balance:** {_as_float(balance.get('total_cash_balance')):.2f}",
                f"**Available:** {_as_float(balance.get('total_available_balance')):.2f}",
                (
                    "**Session unrealised PnL:** "
                    f"{_as_float(balance.get('total_session_unrealized_pnl')):+.2f}"
                ),
                "",
            ]
        )
    positions = portfolio.get("position_balances", [])
    if positions:
        lines.append("| Instrument | Quantity | Market value |")
        lines.append("|---|---|---|")
        for position in sorted(positions, key=lambda p: -_as_float(p.get("market_value"))):
            lines.append(
                f"| {position.get('instrument_name', '?')} "
                f"| {position.get('quantity', '0')} "
                f"| {_as_float(position.get('market_value')):.2f} |"
            )
    else:
        lines.append("_No open crypto positions._")
    return "\n".join(lines).rstrip()


def _as_float(value: object) -> float:
    """Crypto.com reports numbers as strings; coerce defensively."""
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def format_verdict_section(verdict_file: dict, cached: bool) -> str:
    """Render one trader verdict as the SKILL.md scorecard format."""
    symbol = verdict_file.get("symbol", "?")
    date = verdict_file.get("generated_at", "")[:10]
    verdict = verdict_file.get("verdict", {})
    cached_note = " *(cached verdict)*" if cached else ""

    if "parse_error" in verdict or "scorecard" not in verdict:
        return (
            f"### {symbol} — {date}{cached_note}\n\n"
            f"_Judge returned malformed output; raw text preserved in the verdict file._"
        )

    scorecard = verdict["scorecard"]
    bull, bear = scorecard.get("bull", {}), scorecard.get("bear", {})
    lines = [
        f"### {symbol} — {date}{cached_note}",
        "",
        "| Dimension | Bull | Bear |",
        "|---|---|---|",
    ]
    for label, key in _SCORE_DIMENSIONS:
        lines.append(f"| {label} | {bull.get(key, '?')}/10 | {bear.get(key, '?')}/10 |")
    lines.append(
        f"| **Total** | **{bull.get('total', '?')}/50** | **{bear.get('total', '?')}/50** |"
    )
    lines.extend(
        [
            "",
            f"**Winner:** {verdict.get('winner', '?')} ({verdict.get('confidence', '?')} confidence)",
            "",
            f"**Strongest bull argument:** {verdict.get('strongest_bull_argument', '—')}",
            f"**Strongest bear argument:** {verdict.get('strongest_bear_argument', '—')}",
            "",
            f"**Key unresolved question:** {verdict.get('key_unresolved_question', '—')}",
            "",
            f"> {verdict.get('verdict', '')}",
        ]
    )
    return "\n".join(lines)


def generate_summary(report_body: str) -> tuple[str | None, dict]:
    """Ask Claude for a short executive summary of the report body.

    Returns ``(None, {})`` (and logs) when no API key is configured or the call
    fails — the report is still useful without it. A refused call still consumed
    tokens, so its usage is returned even though the summary is dropped.
    """
    logger = get_logger()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        logger.debug("no ANTHROPIC_API_KEY — skipping executive summary")
        return None, {}
    try:
        from anthropic import Anthropic

        client = Anthropic()
        response = client.messages.create(
            model=SUMMARY_MODEL,
            max_tokens=SUMMARY_MAX_TOKENS,
            output_config={"effort": "medium"},
            system=(
                "You write the executive summary paragraph at the top of a daily "
                "personal-finance report. 3-5 sentences, plain prose, no headers. "
                "Lead with the most actionable finding. Not financial advice."
            ),
            messages=[{"role": "user", "content": report_body}],
        )
        used = usage_lib.record(SUMMARY_MODEL, getattr(response, "usage", None))
        if response.stop_reason == "refusal":
            logger.error("summary request was refused — continuing without summary")
            return None, used
        return next((b.text for b in response.content if b.type == "text"), None), used
    except Exception as exc:
        logger.error(f"executive summary failed: {exc} — continuing without summary")
        return None, {}


def build_report(
    date: str,
    analysis_path: str | None,
    tickers_path: str | None,
    portfolio_path: str | None,
    verdicts: list[dict],
    stages: dict,
    with_summary: bool = True,
    pricing: dict | None = None,
    crypto_path: str | None = None,
) -> str:
    """Assemble the full Markdown report.

    Args:
        date:           Run date (YYYY-MM-DD).
        analysis_path:  Path to the news analysis JSON, or None if unavailable.
        tickers_path:   Path to the extracted tickers JSON, or None.
        portfolio_path: Path to the stock portfolio JSON, or None.
        verdicts:       List of ``{"path", "cached"}`` dicts pointing at verdict files.
        stages:         Manifest stage dict for the run-status footer.
        with_summary:   Set False to skip the Claude executive-summary call.
        pricing:        The ``pricing`` config block used to cost the token usage.
        crypto_path:    Path to the crypto portfolio JSON, or None.

    Returns:
        The complete report as a Markdown string.
    """
    logger = get_logger()
    articles = _load_json(analysis_path) if analysis_path else []
    tickers = _load_json(tickers_path) if tickers_path else []
    portfolio = _load_json(portfolio_path) if portfolio_path else None
    crypto = _load_json(crypto_path) if crypto_path else None

    sections = [
        f"# Daily Finance Report — {date}",
        "",
        "## Top news",
        "",
        format_news_section(articles),
        "",
        "## Ticker mentions",
        "",
        format_tickers_section(tickers),
        "",
        "## Portfolio",
        "",
        format_portfolio_section(portfolio),
        "",
        "## Crypto portfolio",
        "",
        format_crypto_section(crypto),
        "",
        "## Trader verdicts",
        "",
    ]
    if verdicts:
        for entry in verdicts:
            sections.append(format_verdict_section(_load_json(entry["path"]), entry["cached"]))
            sections.append("")
    else:
        sections.extend(["_No trader runs today._", ""])

    # The summary is itself a billable call, so the usage section can only be
    # rendered once it has run. Leave a marker and fill it in afterwards.
    sections.extend(["## Token usage", "", _USAGE_MARKER, ""])
    sections.extend(["---", "", "**Run status**", ""])
    for name, stage in stages.items():
        sections.append(f"- {name}: {stage.get('status', '?')}")
    sections.extend(["", "*Generated by the finance-agent daily pipeline — not financial advice.*"])

    body = "\n".join(sections)
    spent, reused = usage_report.split_verdict_usage(verdicts, _load_json)

    if with_summary:
        summary, summary_usage = generate_summary(body.replace(_USAGE_MARKER, ""))
        spent = usage_lib.merge(spent, summary_usage)
        if summary:
            body = body.replace(
                f"# Daily Finance Report — {date}\n",
                f"# Daily Finance Report — {date}\n\n## Summary\n\n{summary.strip()}\n",
                1,
            )
            logger.debug("executive summary added to report")

    return body.replace(_USAGE_MARKER, usage_report.format_usage_section(spent, reused, pricing))
