# finance-agent

A personal financial AI agent powered by Claude. It exposes a set of skills — invoked via slash commands in Claude Code — that fetch market data, analyse financial news, and generate charts.

---

## Skills

### `/check-stock`

Fetches stock quotes and historical price data from Yahoo Finance, then generates ASCII and Jupyter notebook charts.

**Usage**

```
/check-stock --symbol AMZN
/check-stock --symbol HSBA.L --market LSE --period 6mo
```

| Argument   | Required | Default | Description                                              |
|------------|----------|---------|----------------------------------------------------------|
| `--symbol` | Yes      |         | Ticker symbol (e.g. `AMZN`, `TSLA`, `HSBA.L`)           |
| `--market` | No       | —       | Exchange hint (e.g. `NASDAQ`, `LSE`)                     |
| `--period` | No       | `1y`    | Lookback period: `1d 5d 1mo 3mo 6mo 1y 2y 5y 10y ytd max` |

**What it returns**

- Current quote: price, change %, volume, market cap, P/E ratio, 52-week range
- Historical OHLCV data
- ASCII candlestick chart (terminal)
- Jupyter notebook with interactive candlestick chart

---

### `/check-crypto`

Fetches cryptocurrency quotes and OHLC history from CoinGecko, then generates ASCII and Jupyter notebook charts.

**Usage**

```
/check-crypto --coin bitcoin
/check-crypto --coin ethereum --days 30
```

| Argument  | Required | Default | Description                                              |
|-----------|----------|---------|----------------------------------------------------------|
| `--coin`  | Yes      |         | CoinGecko coin ID in lowercase (e.g. `bitcoin`, `shiba-inu`) |
| `--days`  | No       | `365`   | Days of history: `1 7 14 30 90 180 365`                 |

**What it returns**

- Current quote: price, market cap, 24 h volume, ATH/ATL, circulating supply
- Historical OHLC data
- ASCII chart (terminal)
- Jupyter notebook with interactive chart

---

### `/financial-news`

Fetches the latest financial news from 10 RSS feeds (MarketWatch, Yahoo Finance, CNBC, Investing.com, Motley Fool) and ranks articles by keyword match and semantic similarity using a local sentence-transformer model.

**Usage**

```
/financial-news
/financial-news --hours 6
```

| Argument    | Required | Default | Description                              |
|-------------|----------|---------|------------------------------------------|
| `--hours`   | No       | `24`    | Look-back window in hours                |
| `--keywords`| No       | —       | Path to a `keywords.json` config file    |

**What it returns**

- Fetched articles grouped by source, newest first
- Ranked list with keyword score (0–1) and semantic score (0–1)
- Group 1 — keyword match **and** semantic score ≥ 0.45
- Group 2 — semantic score ≥ 0.40 with no keyword match
- An observation paragraph summarising score spread and relevance

---

## Setup

### Prerequisites

- [uv](https://docs.astral.sh/uv/) — Python environment and dependency manager
- Python 3.11+
- [Claude Code](https://claude.ai/claude-code) CLI

### Install

```bash
git clone <repo-url>
cd finance-agent

# Create the virtual environment and install all workspace packages
uv sync --all-packages
```

### Verify

```bash
# Python version
uv run python --version

# Virtual environment
test -d .venv && echo "venv OK"

# Key packages
uv run python -c "import check_stock, check_crypto, financial_news, common" && echo "All packages OK"
```

---

## Development

### Run tests

```bash
uv run pytest                                      # all tests
uv run pytest skills/check_stock/tests/ -v         # single skill
uv run pytest --cov --cov-report=term-missing      # with coverage
```

Coverage threshold is enforced at **85%**.

### Lint and format

```bash
uv run ruff check .
uv run ruff check --fix . && uv run ruff format .
```

### Project layout

```
finance-agent/
├── common/                    # Shared logger and argument parser
│   └── src/common/
├── skills/
│   ├── check_stock/           # Yahoo Finance — quotes, history, charts
│   ├── check_crypto/          # CoinGecko — quotes, history, charts
│   └── financial_news/        # RSS news fetch + semantic ranking
└── pyproject.toml             # uv workspace root
```

Each skill is a uv workspace member with its own `pyproject.toml`, business logic in `src/`, thin script entrypoints in `scripts/`, and tests in `tests/`. Output files (JSON, Jupyter notebooks) are written to each skill's `tmp/` directory.

### Add a new skill

1. Create `skills/<skill_name>/` following the layout above
2. Add a `pyproject.toml` declaring `common` as a dependency
3. Write logic in `src/<skill_name>/` and thin scripts in `scripts/`
4. Write tests in `tests/` (target ≥ 85% coverage)
5. Write a `SKILL.md` with a Step 0 prerequisites check
6. Run `uv sync --all-packages`

See `.claude/rules/skills.md` for the full conventions.
