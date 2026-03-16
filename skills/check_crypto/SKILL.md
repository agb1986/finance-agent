---
name: check-crypto
version: 0.1.0
description: Fetches a cryptocurrency quote, historical OHLC data, and charts for a given coin. Use when the user asks about a specific cryptocurrency's price, performance, history, or chart.
---

# Skill: Check Crypto

Runs a three-step workflow: fetches the current quote, fetches historical OHLC data, then generates charts (ASCII to console + Jupyter notebook).

## When to invoke

Use this skill when the user asks about:
- The current price or performance of a specific cryptocurrency
- Historical price data or charts for a cryptocurrency
- Key metrics (market cap, 24h volume, ATH, circulating supply, etc.)
- Any question referencing a coin by name or ticker (e.g. Bitcoin, ETH, SOL)

## Inputs

| Argument | Required | Default | Description |
|---|---|---|---|
| `--coin` | Yes | — | CoinGecko coin ID, e.g. `bitcoin`, `ethereum`, `solana` |
| `--days` | No | `365` | Days of history to fetch. One of: `1`, `7`, `14`, `30`, `90`, `180`, `365` |

> **Coin ID lookup:** CoinGecko uses lowercase hyphenated IDs (e.g. `bitcoin`, `ethereum`, `shiba-inu`). If the user provides a ticker symbol (e.g. `BTC`, `ETH`), map it to the CoinGecko ID before invoking the scripts.

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
uv run python -c "import check_crypto, pycoingecko, mplfinance, plotext, nbformat, common" && echo "All packages OK"
```

---

### Step 1 — Fetch the current quote

```bash
uv run skills/check_crypto/scripts/fetch_quote.py --coin <COIN_ID>
```

The script prints the path to the output JSON file, e.g.:
```
skills/check_crypto/tmp/check_crypto_bitcoin_20260316_090000.json
```

Read the file. It contains:

```json
{
  "coin_id":            "bitcoin",
  "symbol":             "BTC",
  "name":               "Bitcoin",
  "price":              65000.00,
  "currency":           "USD",
  "market_cap":         1280000000000,
  "volume_24h":         35000000000,
  "change_24h":         1200.00,
  "change_percent_24h": 1.88,
  "ath":                73750.00,
  "atl":                67.81,
  "circulating_supply": 19680000.0,
  "total_supply":       21000000.0,
  "fetched_at":         "2026-03-16T09:00:00Z"
}
```

---

### Step 2 — Fetch historical OHLC data

```bash
uv run skills/check_crypto/scripts/fetch_history.py --coin <COIN_ID> [--days <DAYS>]
```

The script prints the path to the output JSON file, e.g.:
```
skills/check_crypto/tmp/history_bitcoin_365d_20260316_090000.json
```

Read the file. It contains a `bars` array of daily OHLC records:

```json
{
  "coin_id": "bitcoin",
  "days": 365,
  "bars": [
    { "date": "2025-03-17", "open": 84000.0, "high": 86000.0, "low": 83000.0, "close": 85500.0 }
  ]
}
```

---

### Step 3 — Generate charts

```bash
uv run skills/check_crypto/scripts/chart_history.py --input <path/to/history.json>
```

This script:
- Renders an ASCII line chart of closing prices to the console
- Writes a Jupyter notebook (`.ipynb`) with pre-rendered candlestick, line, and OHLC charts to `tmp/`

The script prints the path to the notebook, e.g.:
```
skills/check_crypto/tmp/chart_bitcoin_365d_20260316_090100.ipynb
```

---

### Step 4 — Present output to the user

Combine all three outputs into a single response using **exactly** this format:

```markdown
## <Name> (<SYMBOL>) — <fetched_at date only>

**Price:** <price> <currency> (<change_24h> / <change_percent_24h>%)
**24h Volume:** <volume_24h>
**Market Cap:** <market_cap>
**ATH:** <ath> | **ATL:** <atl>
**Circulating Supply:** <circulating_supply>

---

<ASCII chart output — copy exactly as printed to console>

---

**Generated files:**
- Quote: `<path to check_crypto_*.json>`
- History: `<path to history_*.json>`
- Notebook: `<path to chart_*.ipynb>`

> Open the notebook: `jupyter notebook <path to chart_*.ipynb>`
```

Format `market_cap` and `volume_24h` in human-readable form (e.g. `$1.28T`, `$35B`). Format `change_percent_24h` with 2 decimal places and a `+` prefix when positive. If any field is `null`, omit that line.

---

## Sources

Data provided by [CoinGecko](https://www.coingecko.com/) via [pycoingecko](https://github.com/man-c/pycoingecko).
