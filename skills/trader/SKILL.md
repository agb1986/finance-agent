---
name: trader
version: 0.1.0
description: >
  Runs a full multi-agent TradingAgents analysis for a stock and produces a BUY/HOLD/SELL
  recommendation with a detailed markdown report. Uses four analyst agents (market, social,
  news, fundamentals) plus a bull/bear investment debate, risk assessment, and a final
  portfolio-manager decision — all powered by Claude via Anthropic.
---

# Skill: Trader

Runs the [TradingAgents](https://github.com/tauricresearch/tradingagents) multi-agent pipeline
to analyse a stock and determine whether it is a **BUY**, **HOLD**, or **SELL**.

The pipeline runs four analyst agents in parallel (market, social sentiment, news, fundamentals),
holds a bull/bear investment debate, conducts a risk assessment, and issues a final trade decision.
All agents run on Claude (Anthropic) via LangChain.

## When to invoke

Use this skill when the user asks:
- Should I buy/sell/hold `<TICKER>`?
- Give me a trading analysis of `<TICKER>`
- What do the agents think about `<TICKER>`?
- Run a TradingAgents analysis on `<TICKER>`

## Required environment variables

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Authenticates all LLM calls (Claude models) |

If the key is missing the script exits with a clear error message.

## Inputs

| Argument | Required | Default | Description |
|---|---|---|---|
| `--symbol` | Yes | — | Ticker symbol, e.g. `NVDA`, `TSLA`, `AAPL` |
| `--date` | No | today (UTC) | Analysis date in `YYYY-MM-DD` format |

---

## How to invoke

### Step 0 — Verify prerequisites

Run these checks before any other step. If any command fails, report the error to the user and
ask whether you should self-heal by running `uv sync --all-packages`.

```bash
# Python is available via uv
uv run python --version

# Root venv exists
test -d .venv && echo "venv OK" || echo "ERROR: .venv not found"

# Required packages are importable
uv run python -c "import trader, tradingagents, common" && echo "All packages OK"
```

---

### Step 1 — Run the analysis

```bash
uv run skills/trader/scripts/analyze_stock.py --symbol <SYMBOL> [--date <YYYY-MM-DD>]
```

This runs the full TradingAgents pipeline. Expect it to take **2–5 minutes** as multiple LLM
agents run in sequence.

The script prints the path to the output markdown report, e.g.:
```
skills/trader/tmp/trader_NVDA_2026-01-15_20260115_100000.md
```

Read the file. It contains the full markdown report with all analyst write-ups and the final
decision.

---

### Step 2 — Present output to the user

Read the markdown report file and present it to the user using **exactly** this structure:

```markdown
## Trading Analysis: <SYMBOL> — <trade_date>

**Decision:** <BUY / HOLD / SELL>

---

### Executive Summary
<trader_plan section from the report>

### Market Analysis
<brief summary — 2–3 sentences>

### Sentiment & News
<brief summary — 2–3 sentences>

### Fundamentals
<brief summary — 2–3 sentences>

### Investment Debate
<brief summary of bull vs bear conclusions>

### Risk Assessment
<brief summary — 1–2 sentences>

### Final Decision
<final_decision section from the report verbatim>

---

**Full report saved to:** `<path to .md file>`
```

Keep each section summary concise. Reproduce the Final Decision text verbatim.

---

## Sources

Analysis powered by [TradingAgents](https://github.com/tauricresearch/tradingagents)
using data from yfinance (Yahoo Finance). LLM: Claude via Anthropic.
