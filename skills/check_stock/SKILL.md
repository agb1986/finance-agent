---
name: check-stock
version: 0.1.0
description: Fetches the current quote and key details for a given stock symbol. Use when the user asks about a specific stock's current price, performance, or fundamentals.
---

# Skill: Check Stock

Fetches the current quote and key details for a given stock symbol and writes the result to a JSON file.

## When to invoke

Use this skill when the user asks about:
- The current price of a stock
- How a specific stock is performing today
- Key fundamentals for a stock (P/E ratio, market cap, 52-week range, etc.)
- Any question referencing a ticker symbol

## How to invoke

### Step 1 — Run the check_stock script

```bash
uv run skills/check_stock/scripts/fetch_quote.py --symbol <SYMBOL>
uv run skills/check_stock/scripts/fetch_quote.py --symbol <SYMBOL> --market <MARKET>
```

Arguments:
- `--symbol` (required) — ticker symbol, e.g. `AMZN`
- `--market` (optional) — exchange or market, e.g. `NASDAQ`. Use when the user specifies one or when the symbol is ambiguous.

The script will print the path to the output file on stdout, e.g.:
```
skills/check_stock/tmp/check_stock_AMZN_20260316_090000.json
```

### Step 2 — Read the output file

Read the file path returned in Step 1. It contains a JSON object with the following fields:

```json
{
  "symbol":         "AMZN",
  "market":         "NASDAQ",
  "fetched_at":     "2026-03-16T09:00:00Z",
  "name":           "Amazon.com, Inc.",
  "price":          185.50,
  "currency":       "USD",
  "change":         2.30,
  "change_percent": 1.25,
  "volume":         32000000,
  "market_cap":     1950000000000,
  "pe_ratio":       38.2,
  "week_52_high":   230.00,
  "week_52_low":    151.61
}
```

Unknown or unavailable fields will be `null`.

### Step 3 — Summarise for the user

Present the quote in a concise, readable format. Include:
- Current price and currency
- Change vs. previous close (absolute and percentage)
- Key fundamentals: market cap, P/E ratio, 52-week range
- Volume if notable

## Sources

> **Note:** The data source is not yet configured. `fetch_quote` in `src/check_stock/fetcher.py` is a stub pending API provider selection (e.g. yfinance, Alpha Vantage, Polygon.io).
