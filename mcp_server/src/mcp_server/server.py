"""Finance Agent MCP Server — exposes all skills as MCP tools via SSE transport."""

import json
import os
import subprocess
from pathlib import Path

from mcp.server.fastmcp import FastMCP

REPO_ROOT = Path(os.environ.get("REPO_ROOT", Path.cwd()))
PORT = int(os.environ.get("MCP_PORT", "35001"))
HOST = os.environ.get("MCP_HOST", "0.0.0.0")

mcp = FastMCP("Finance Agent", host=HOST, port=PORT)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _run(script: str, args: list[str]) -> str:
    """Run a skill script via uv run and return stripped stdout."""
    result = subprocess.run(
        ["uv", "run", script, *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or f"exit code {result.returncode}"
        raise RuntimeError(f"Script '{script}' failed: {detail}")
    return result.stdout.strip()


def _read_json(file_path: str) -> dict | list:
    """Read a JSON file written by a skill script."""
    path = REPO_ROOT / file_path
    return json.loads(path.read_text())


def _first_line(output: str) -> tuple[str, str]:
    """Split script output into (file_path, remainder)."""
    parts = output.split("\n", 1)
    return parts[0].strip(), (parts[1].strip() if len(parts) > 1 else "")


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def check_stock(symbol: str, market: str = "", period: str = "1y") -> str:
    """Fetch the current quote and historical price data for a stock.

    Args:
        symbol: Ticker symbol, e.g. AMZN, MSFT, HSBA.L
        market: Exchange/market, e.g. NASDAQ. Leave blank if not needed.
        period: History lookback — one of: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max
    """
    quote_args = ["--symbol", symbol]
    if market:
        quote_args += ["--market", market]

    quote_path = _run("skills/check_stock/scripts/fetch_quote.py", quote_args)
    quote = _read_json(quote_path)

    history_args = ["--symbol", symbol, "--period", period]
    if market:
        history_args += ["--market", market]

    history_path = _run("skills/check_stock/scripts/fetch_history.py", history_args)
    history = _read_json(history_path)

    return json.dumps({"quote": quote, "history": history})


@mcp.tool()
def check_crypto(coin: str, days: int = 365) -> str:
    """Fetch the current quote and historical OHLC data for a cryptocurrency.

    Args:
        coin: CoinGecko coin ID, e.g. bitcoin, ethereum, solana
        days: Days of history — one of: 1, 7, 14, 30, 90, 180, 365
    """
    quote_path = _run("skills/check_crypto/scripts/fetch_quote.py", ["--coin", coin])
    quote = _read_json(quote_path)

    history_path = _run(
        "skills/check_crypto/scripts/fetch_history.py",
        ["--coin", coin, "--days", str(days)],
    )
    history = _read_json(history_path)

    return json.dumps({"quote": quote, "history": history})


@mcp.tool()
def get_stock_portfolio() -> str:
    """Fetch the user's Trading212 stock portfolio — account summary and open positions.

    Requires TRADING_212_API_KEY and TRADING_212_API_SECRET environment variables.
    """
    output = _run("skills/get_stock_portfolio/scripts/fetch_portfolio.py", [])
    file_path, report = _first_line(output)
    data = _read_json(file_path)
    return json.dumps({"data": data, "report": report})


@mcp.tool()
def get_crypto_portfolio() -> str:
    """Fetch the user's Crypto.com Exchange portfolio — account balances and open positions.

    Requires CRYPTO_API_KEY and CRYPTO_API_SECRET environment variables.
    """
    output = _run("skills/get_crypto_portfolio/scripts/fetch_portfolio.py", [])
    file_path, report = _first_line(output)
    data = _read_json(file_path)
    return json.dumps({"data": data, "report": report})


@mcp.tool()
def get_financial_news(hours: int = 24) -> str:
    """Fetch recent financial news from multiple RSS feeds.

    Args:
        hours: How many hours back to look for articles (default: 24)
    """
    news_path = _run("skills/financial_news/scripts/fetch_news.py", ["--hours", str(hours)])
    articles = _read_json(news_path)
    return json.dumps(articles)


@mcp.tool()
def analyze_financial_news(hours: int = 24, min_semantic: float = 0.40) -> str:
    """Fetch and rank financial news articles by relevance to your configured keywords.

    Articles are scored by keyword match rate and semantic similarity.

    Args:
        hours: How many hours back to fetch news before analysing (default: 24)
        min_semantic: Minimum semantic similarity score to include (0.0–1.0, default: 0.40)
    """
    news_path = _run("skills/financial_news/scripts/fetch_news.py", ["--hours", str(hours)])
    analysis_path = _run(
        "skills/financial_news/scripts/analyze_news.py",
        ["--input", news_path, "--min-semantic", str(min_semantic)],
    )
    articles = _read_json(analysis_path)
    return json.dumps(articles)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport="sse")
