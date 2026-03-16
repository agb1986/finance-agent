---
name: check-stock
version: 0.2.0
description: Fetches a stock quote, historical OHLCV data, and charts for a given symbol. Use when the user asks about a specific stock's price, performance, history, or chart.
---

# Skill: Check Stock

Runs a three-step workflow: fetches the current quote, fetches historical price data, then generates charts (ASCII to console + Jupyter notebook).

## When to invoke

Use this skill when the user asks about:
- The current price or performance of a specific stock
- Historical price data or charts for a stock
- Key fundamentals (P/E ratio, market cap, 52-week range, etc.)
- Any question referencing a ticker symbol

## Inputs

| Argument | Required | Default | Description |
|---|---|---|---|
| `--symbol` | Yes | — | Ticker symbol, e.g. `AMZN`, `BTC-USD`, `HSBA.L` |
| `--market` | No | — | Exchange/market, e.g. `NASDAQ`. Use when the user specifies one or the symbol is ambiguous. |
| `--period` | No | `1y` | History lookback period. One of: `1d`, `5d`, `1mo`, `3mo`, `6mo`, `1y`, `2y`, `5y`, `10y`, `ytd`, `max` |

---

## How to invoke

### Step 1 — Fetch the current quote

```bash
uv run skills/check_stock/scripts/fetch_quote.py --symbol <SYMBOL> [--market <MARKET>]
```

The script prints the path to the output JSON file, e.g.:
```
skills/check_stock/tmp/check_stock_AMZN_20260316_090000.json
```

Read the file. It contains:

```json
{
  "symbol":         "AMZN",
  "market":         "NASDAQ",
  "fetched_at":     "2026-03-16T09:00:00Z",
  "name":           "Amazon.com, Inc.",
  "price":          207.67,
  "currency":       "USD",
  "change":         -1.86,
  "change_percent": -0.8877,
  "volume":         35662137,
  "market_cap":     2229321072640,
  "pe_ratio":       29.0,
  "week_52_high":   258.60,
  "week_52_low":    161.38
}
```

---

### Step 2 — Fetch historical price data

```bash
uv run skills/check_stock/scripts/fetch_history.py --symbol <SYMBOL> [--market <MARKET>] [--period <PERIOD>]
```

The script prints the path to the output JSON file, e.g.:
```
skills/check_stock/tmp/history_AMZN_1y_20260316_090000.json
```

Read the file. It contains a `bars` array of daily OHLCV records:

```json
{
  "symbol": "AMZN",
  "market": "NASDAQ",
  "period": "1y",
  "fetched_at": "2026-03-16T09:00:00Z",
  "bars": [
    { "date": "2025-03-17", "open": 190.00, "high": 195.00, "low": 188.50, "close": 193.20, "volume": 28000000 }
  ]
}
```

---

### Step 3 — Generate charts

```bash
uv run skills/check_stock/scripts/chart_history.py --input <path/to/history.json>
```

This script:
- Renders an ASCII line chart of closing prices to the console
- Writes a Jupyter notebook (`.ipynb`) with pre-rendered candlestick, line, and OHLC charts to `tmp/`

The script prints the path to the notebook, e.g.:
```
skills/check_stock/tmp/chart_AMZN_1y_20260316_090100.ipynb
```

---

### Step 4 — Present output to the user

Combine all three outputs into a single response using **exactly** this format:

```markdown
## <Name> (<SYMBOL>) — <fetched_at date only>

**Price:** <price> <currency> (<change> / <change_percent>%)
**Volume:** <volume>
**Market Cap:** <market_cap>
**P/E Ratio:** <pe_ratio>
**52-week range:** <week_52_low> – <week_52_high>

---

<ASCII chart output — copy exactly as printed to console>

---

**Generated files:**
- Quote: `<path to check_stock_*.json>`
- History: `<path to history_*.json>`
- Notebook: `<path to chart_*.ipynb>`

> Open the notebook: `jupyter notebook <path to chart_*.ipynb>`
```

Format `market_cap` in human-readable form (e.g. `$2.23T`, `$450B`). Format `change_percent` with 2 decimal places and a `+` prefix when positive. If any field is `null`, omit that line.

---

## Sources

Data provided by [yfinance](https://github.com/ranaroussi/yfinance) via Yahoo Finance.
