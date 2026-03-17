---
name: get-stock-portfolio
version: 0.1.0
description: Fetches the user's Trading212 stock portfolio — account summary and open positions. Use when the user asks about their portfolio, account value, positions, or P&L.
---

# Skill: Get Stock Portfolio

Fetches the user's Trading212 equity portfolio by calling the Trading212 API and combines an account summary with all open positions into a JSON file plus a human-readable report.

## When to invoke

Use this skill when the user asks about:
- Their Trading212 portfolio or account
- Open positions or holdings
- Account value, invested amount, or P&L
- Unrealised or realised P&L across their portfolio

## Prerequisites

Set the following environment variables before invoking:

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
uv run python -c "import get_stock_portfolio, requests, common" && echo "All packages OK"

# API credentials are set
test -n "$TRADING_212_API_KEY" && echo "API key OK" || echo "ERROR: TRADING_212_API_KEY not set"
test -n "$TRADING_212_API_SECRET" && echo "API secret OK" || echo "ERROR: TRADING_212_API_SECRET not set"
```

---

### Step 1 — Fetch portfolio

```bash
uv run skills/get_stock_portfolio/scripts/fetch_portfolio.py
```

The script prints the path to the output JSON file, followed by a human-readable report:

```
skills/get_stock_portfolio/tmp/portfolio_20260317_100000.json

## Trading212 Portfolio — 2026-03-17

### Account Summary
  Currency:       GBP
  Total Value:    249.11
  Invested:       249.62
  Unrealised P&L: -0.52
  Realised P&L:   +1,366.48

### Open Positions (3)

  Name                            ISIN            Date Bought   Shares      Price       Total Cost     Current Value    P&L
  ------------------------------  --------------  ------------  ----------  ----------  -------------  ---------------  --------------
  Amazon                          US0231351067    16/03/2026    0.7952      210.80      124.81         125.74           +0.93
  SoundHound AI                   US8361001071    16/03/2026    13.2158     7.50        74.89          74.35            -0.54
  Sun Communities                 US8666741041    16/03/2026    0.4842      134.94      49.92          49.01            -0.91
```

Read the JSON file for the full raw API response:

```json
{
  "fetched_at": "2026-03-17T10:00:00Z",
  "account_summary": {
    "id": 12345,
    "currency": "GBP",
    "totalValue": 249.11,
    "cash": {
      "availableToTrade": 0.01,
      "reservedForOrders": 0,
      "inPies": 0
    },
    "investments": {
      "currentValue": 249.10,
      "totalCost": 249.62,
      "realizedProfitLoss": 1366.48,
      "unrealizedProfitLoss": -0.52
    }
  },
  "positions": [
    {
      "instrument": {
        "ticker": "AMZN_US_EQ",
        "name": "Amazon",
        "isin": "US0231351067",
        "currency": "USD"
      },
      "createdAt": "2026-03-16T15:30:04.319+02:00",
      "quantity": 0.79523509,
      "currentPrice": 210.80,
      "averagePricePaid": 208.55,
      "walletImpact": {
        "currency": "GBP",
        "totalCost": 124.81,
        "currentValue": 125.74,
        "unrealizedProfitLoss": 0.93,
        "fxImpact": -0.41
      }
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
**Currency:** <currency>
**Total Value:** <totalValue>
**Invested:** <investments.totalCost>
**Unrealised P&L:** <investments.unrealizedProfitLoss>
**Realised P&L:** <investments.realizedProfitLoss>

---

### Open Positions (<count>)

| Name | ISIN | Date Bought | Shares | Price | Total Cost | Current Value | P&L |
|---|---|---|---|---|---|---|---|
| <name> | <isin> | <DD/MM/YYYY> | <quantity> | <currentPrice> | <walletImpact.totalCost> | <walletImpact.currentValue> | <currentValue - totalCost> |

---

**Generated file:** `<path to portfolio_*.json>`
```

Format currency values to 2 decimal places. Use a `+` prefix for positive P&L values. Omit the positions table if there are no open positions. Positions are sorted by current value descending.

---

## Sources

Data provided by the [Trading212 API](https://docs.trading212.com/api).
