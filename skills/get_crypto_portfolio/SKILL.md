---
name: get-crypto-portfolio
version: 0.1.1
description: Fetches the user's Crypto.com Exchange portfolio — account balance and open positions. Use when the user asks about their crypto portfolio, balances, or open positions.
---

# Skill: Get Crypto Portfolio

Fetches the user's Crypto.com Exchange portfolio by calling the private REST API. Combines account balance with all open positions into a JSON file plus a human-readable report.

## When to invoke

Use this skill when the user asks about:
- Their Crypto.com portfolio or account
- Open crypto positions or holdings
- Crypto account balance or margin balance
- Unrealised or realised P&L on their crypto positions

## Prerequisites

Set the following environment variables before invoking:

| Variable | Description |
|---|---|
| `CRYPTO_API_KEY` | Your Crypto.com Exchange API key |
| `CRYPTO_API_SECRET` | Your Crypto.com Exchange API secret |

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
uv run python -c "import get_crypto_portfolio, requests, common" && echo "All packages OK"

# API credentials are set
test -n "$CRYPTO_API_KEY" && echo "API key OK" || echo "ERROR: CRYPTO_API_KEY not set"
test -n "$CRYPTO_API_SECRET" && echo "API secret OK" || echo "ERROR: CRYPTO_API_SECRET not set"
```

---

### Step 1 — Fetch portfolio

```bash
uv run skills/get_crypto_portfolio/scripts/fetch_portfolio.py
```

The script prints the path to the output JSON file, followed by a human-readable report:

```
skills/get_crypto_portfolio/tmp/portfolio_20260317_100000.json

## Crypto.com Portfolio — 2026-03-17

### Account Balance

  Currency      Cash Balance      Margin Balance    Available         Unrealised PnL    Realised PnL
  ------------  ----------------  ----------------  ----------------  ----------------  --------------
  USD           116.89            116.89            109.58            0.00              0.00

### Open Positions (1)

  Name          Quantity          Market Value      Collateral Amount    P/L
  ------------  ----------------  ----------------  ------------------  --------------
  BTC           0.00              116.96            109.65              +7.31
```

Read the JSON file for the full raw API response:

```json
{
  "fetched_at": "2026-03-17T10:00:00Z",
  "balances": [
    {
      "instrument_name": "USD",
      "total_cash_balance": "116.89",
      "total_margin_balance": "116.89",
      "total_available_balance": "109.58",
      "total_session_unrealized_pnl": "0.00",
      "total_session_realized_pnl": "0.00",
      "position_balances": [
        {
          "instrument_name": "BTC",
          "quantity": "0.0015775",
          "market_value": "116.96321692",
          "collateral_amount": "109.65301586"
        }
      ]
    }
  ],
  "position_balances": [
    {
      "instrument_name": "BTC",
      "quantity": "0.0015775",
      "market_value": "116.96321692",
      "collateral_amount": "109.65301586"
    }
  ]
}
```

---

### Step 2 — Present output to the user

Present the human-readable summary printed by the script using **exactly** this format:

```markdown
## Crypto.com Portfolio — <date>

### Account Balance

| Currency | Cash Balance | Margin Balance | Available | Unrealised PnL | Realised PnL |
|---|---|---|---|---|---|
| <instrument_name> | <total_cash_balance> | <total_margin_balance> | <total_available_balance> | <total_session_unrealized_pnl> | <total_session_realized_pnl> |

---

### Open Positions (<count>)

| Name | Quantity | Market Value | Collateral Amount | P/L |
|---|---|---|---|---|
| <instrument_name> | <quantity> | <market_value> | <collateral_amount> | <market_value - collateral_amount> |

---

**Generated file:** `<path to portfolio_*.json>`
```

Format numeric values to 2 decimal places. Use a `+` prefix for positive P/L values. Omit the positions table if there are no open positions. Positions are sorted by market value descending. P/L = market_value − collateral_amount.

---

## Sources

Data provided by the [Crypto.com Exchange API](https://exchange-docs.crypto.com/exchange/v1/rest-ws/index.html).
