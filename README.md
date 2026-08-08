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

Fetches the latest financial news from 10 RSS feeds (MarketWatch, Yahoo Finance, CNBC, Investing.com, Motley Fool), removes duplicates syndicated across feeds, and ranks articles by keyword match and semantic similarity using a local sentence-transformer model.

**Usage**

```
/financial-news
/financial-news --hours 6
/financial-news --min-semantic 0.40
```

| Argument         | Required | Default | Description                                    |
|------------------|----------|---------|------------------------------------------------|
| `--hours`        | No       | `24`    | Look-back window in hours                      |
| `--keywords`     | No       | —       | Path to a `keywords.json` config file          |
| `--min-semantic` | No       | —       | Only include articles with semantic score ≥ N  |
| `--min-keyword`  | No       | —       | Only include articles with keyword score ≥ N   |

**What it returns**

- Fetched articles grouped by source, newest first, deduplicated by URL/title
- Ranked list with keyword score (0–1; capped count — 1 match = 0.33, 3+ = 1.0) and semantic score (0–1)
- Group 1 — keyword match **and** semantic score ≥ 0.45
- Group 2 — semantic score ≥ 0.40 with no keyword match
- An observation paragraph summarising score spread and relevance

---

### `/get-stock-portfolio`

Fetches the user's Trading212 equity portfolio — account summary and all open positions — via the Trading212 API.

**Usage**

```
/get-stock-portfolio
```

No arguments. Requires `TRADING_212_API_KEY` and `TRADING_212_API_SECRET` environment variables.

**What it returns**

- Account summary: currency, total value, invested amount, unrealised and realised P&L
- Open positions table: name, ISIN, date bought, shares, current price, total cost, current value, P&L
- Raw JSON file written to `tmp/`

---

### `/get-crypto-portfolio`

Fetches the user's Crypto.com Exchange portfolio — account balance and all open positions — via the Crypto.com private REST API.

**Usage**

```
/get-crypto-portfolio
```

No arguments. Requires `CRYPTO_API_KEY` and `CRYPTO_API_SECRET` environment variables.

**What it returns**

- Account balance table: currency, cash balance, margin balance, available balance, unrealised and realised PnL
- Open positions table: instrument, type, quantity, cost, unrealised PnL, realised PnL
- Raw JSON file written to `tmp/`

---

### `/trader`

Runs a multi-agent investment analysis for a symbol: a five-role analyst panel (fundamental, technical, macro, sentiment, risk) in parallel, a fixed-rounds bull/bear debate over the panel's findings, and an impartial judge that scores the debate and returns a structured verdict.

**Usage**

```
/trader --symbol AMZN
```

| Argument         | Required | Default | Description                                        |
|------------------|----------|---------|----------------------------------------------------|
| `--symbol`       | Yes      |         | Ticker symbol to analyse                           |
| `--context-file` | No       | —       | Market data file to ground the panel (quote/history) |
| `--rounds`       | No       | `2`     | Debate rounds                                      |

**What it returns**

- Panel briefs, debate transcript, and a judge scorecard (evidence quality, rebuttal validity, risk-adjusted logic, internal consistency, falsifiability) with winner, confidence, and an actionable verdict
- The verdict JSON is schema-enforced via structured outputs

> Each full run makes 10 Anthropic API calls (5× Sonnet panel, 4× Opus debate, 1× Opus judge), measured at ~$0.16. Models and prompts live in `skills/trader/config/roles.yaml`.

---

### `/daily-pipeline`

Orchestrates everything into one checkpointed daily run: fetch + rank news, extract top ticker mentions, fetch portfolios, ground the trader with `check_stock` market data, run it on the most relevant symbols, build a Markdown report (with token usage and estimated cost), and email it. Re-running the same day resumes from the first incomplete stage; on failure it sends a best-effort alert email.

```
uv run skills/daily_pipeline/scripts/run_daily.py [--dry-run] [--skip-email] [--no-summary]
```

Thresholds, caps, and pricing live in `skills/daily_pipeline/pipeline.yaml`. See `skills/daily_pipeline/SKILL.md` for the full stage list and `docs/deployment.md` for running it on a schedule.

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
uv run python -c "import check_stock, check_crypto, financial_news, get_stock_portfolio, get_crypto_portfolio, trader, daily_pipeline, mcp_server, common" && echo "All packages OK"
```

---

## Deployment

The `/daily-pipeline` skill is designed to run unattended on a home server
(CasaOS): cron fires a one-shot container once a day, which fetches news, runs
the trader on the most relevant symbols, builds a Markdown report, and emails it.

```bash
cp .env.example .env && $EDITOR .env   # API keys, SMTP, timezone
docker compose build

# Preview without spending anything
docker compose run --rm finance-pipeline \
  uv run skills/daily_pipeline/scripts/run_daily.py --dry-run

# Full run, as cron will invoke it
docker compose run --rm finance-pipeline
```

The same image also serves the MCP server (`docker compose up -d finance-mcp`),
a long-running service on `127.0.0.1:35001`. The pipeline sits behind a Compose
profile so `docker compose up` does not start it.

See **[docs/deployment.md](docs/deployment.md)** for the full guide — Gmail app
passwords, the cron entry, reading reports out of the named volumes, and cost
tuning.

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
│   ├── financial_news/        # RSS news fetch + semantic ranking
│   ├── get_stock_portfolio/   # Trading212 portfolio — account summary + positions
│   ├── get_crypto_portfolio/  # Crypto.com portfolio — account balance + positions
│   ├── trader/                # Analyst panel → debate → judge verdict
│   └── daily_pipeline/        # Checkpointed orchestrator — news → trader → report → email
├── mcp_server/                # Exposes all skills as MCP tools over SSE
├── Dockerfile                 # One image: MCP server + daily pipeline
├── docker-compose.yml
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
