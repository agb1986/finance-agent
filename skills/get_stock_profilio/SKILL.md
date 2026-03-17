---
name: get-stock-profilio
version: 0.1.0
description: Fetches the user's Trading212 stock portfolio — account summary and open positions. Use when the user asks about their portfolio, account value, positions, or P&L.
---

# Skill: Get Stock Portfolio

Fetches the user's Trading212 equity portfolio by calling the Trading212 API and combines an account summary with all open positions into a JSON file plus a human-readable report.

## When to invoke

Use this skill when the user asks about:
- Their Trading212 portfolio or account
- Open positions or holdings
- Account value, invested amount, or free cash
- Unrealised or realised P&L across their portfolio

## Prerequisites

Set the following environment variable before invoking:

| Variable | Description |
|---|---|
| `TRADING_212_API_KEY` | Your Trading212 API key (from the Trading212 app → Settings → API) |
| `TRADING_212_API_SECRET` | Your Trading212 API secret (from the Trading212 app → Settings → API) |

---

## How to invoke

### Step 0 — Verify prerequisites

Run these checks before any other step. If any command fails, report the error to the user and ask whether you should self-heal by running `uv sync --all-packages`.

```bash
# Python is available via uv
uv run python --version

# Root venv exists
test -d .venv && echo "venv OK" || echo "ERROR: .venv not found"

# Required packages are importable
uv run python -c "import get_stock_profilio, requests, common" && echo "All packages OK"

# API credentials are set
test -n "$TRADING_212_API_KEY" && echo "API key OK" || echo "ERROR: TRADING_212_API_KEY not set"
test -n "$TRADING_212_API_SECRET" && echo "API secret OK" || echo "ERROR: TRADING_212_API_SECRET not set"
```

---

### Step 1 — Fetch portfolio

```bash
uv run skills/get_stock_profilio/scripts/fetch_portfolio.py
```

The script prints the path to the output JSON file, followed by a human-readable summary:

```
skills/get_stock_profilio/tmp/portfolio_20260317_100000.json

## Trading212 Portfolio — 2026-03-17

### Account Summary
  Total Value:    5,500.00
  Invested:       5,000.00
  Free Cash:      500.00
  Unrealised P&L: +200.00 (+4.00%)
  Realised P&L:   +50.00

### Open Positions (2)

  AAPL_US_EQ                     qty=10.0000  price=170.0000  value=1,700.00  P&L=+200.00 (+13.33%)
  TSLA_US_EQ                     qty=5.0000   price=180.0000  value=900.00    P&L=-100.00 (-10.00%)
```

Read the JSON file for the full raw API response:

```json
{
  "fetched_at": "2026-03-17T10:00:00Z",
  "account_summary": {
    "cash": {
      "free": 500.00,
      "total": 5500.00,
      "ppl": 200.00,
      "result": 50.00,
      "invested": 5000.00,
      "pieCash": 0.00
    },
    "open": { "unfinalised": 0, "total": 2 }
  },
  "positions": [
    {
      "ticker": "AAPL_US_EQ",
      "quantity": 10.0,
      "averagePrice": 150.00,
      "currentPrice": 170.00,
      "ppl": 200.00,
      "initialFillDate": "2024-01-15T10:30:00Z"
    }
  ]
}
```

---

### Step 2 — Present output to the user

Present the human-readable summary printed by the script using **exactly** this format:

```markdown
## Trading212 Portfolio — <date>

### Account Summary
**Total Value:** <total>
**Invested:** <invested>
**Free Cash:** <free>
**Unrealised P&L:** <ppl> (<ppl_pct>%)
**Realised P&L:** <result>

---

### Open Positions (<count>)

| Ticker | Qty | Price | Value | P&L |
|---|---|---|---|---|
| <ticker> | <qty> | <price> | <value> | <ppl> (<ppl_pct>%) |

---

**Generated file:** `<path to portfolio_*.json>`
```

Format currency values to 2 decimal places. Use a `+` prefix for positive P&L values. Omit the positions table if there are no open positions.

---

## Sources

Data provided by the [Trading212 API](https://docs.trading212.com/api).
