---
name: daily-pipeline
version: 0.1.2
description: Runs the full daily finance pipeline — fetches and ranks news, extracts top ticker mentions, fetches portfolios, runs the trader on the most relevant symbols, builds a Markdown report, and emails it. Use when the user asks for the daily report, the full pipeline, or a morning briefing.
---

# Skill: Daily Pipeline

Orchestrates the other skills into one checkpointed daily run:

```
fetch_news → analyze_news → extract_tickers ─┐
stock_portfolio → select_candidates ─────────┼→ trader (per symbol) → build_report → send_email
crypto_portfolio (artifact only, v1) ────────┘
```

Each run writes to `tmp/run_<YYYYMMDD>/` with a `manifest.json` checkpoint —
re-running the same day resumes from the first incomplete stage, so a crash or
a cron re-fire never repeats completed API spend. Trader verdicts newer than
`trader.verdict_cache_days` (in `pipeline.yaml`) are reused instead of re-run.

Thresholds and caps live in `pipeline.yaml`; company-name → ticker mappings in
`ticker_map.json`. Edit both without touching code.

> **Cost note:** each trader run makes 10 API calls (5× Sonnet, 5× Opus),
> measured at ~$0.16. `trader.max_runs` (default 2) caps the daily total at
> roughly $0.35 including the ~$0.02 executive summary; the verdict cache cuts
> repeat spend further. Every report ends with a **Token usage** table showing actual
> tokens and estimated cost per model, so the real figure is measured rather
> than assumed. Rates live in `pipeline.yaml` under `pricing` — a model with no
> configured rate still has its tokens counted but is named as unpriced.
>
> Tokens attached to a *cached* verdict were charged on an earlier day, so they
> are reported on a separate line rather than added to today's total.

## When to invoke

Use this skill when the user asks:
- For the daily report / morning briefing / "run the pipeline"
- To re-send or rebuild today's report
- To preview what the pipeline would do (`--dry-run`)

## Inputs

| Argument | Script | Required | Default | Description |
|---|---|---|---|---|
| `--dry-run` | run_daily | No | off | Print the plan, execute nothing |
| `--date` | run_daily | No | today | Run date `YYYYMMDD` (resume a past run) |
| `--max-trader-runs` | run_daily | No | `pipeline.yaml` | Cap trader pipelines this run |
| `--skip-email` | run_daily | No | off | Build the report but do not send |
| `--no-summary` | run_daily | No | off | Skip the Claude executive summary |

## Environment

| Variable | Required | Used by |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | trader stages + executive summary |
| `TRADING_212_API_KEY` / `TRADING_212_API_SECRET` | No — stage skipped if unset | stock portfolio |
| `CRYPTO_API_KEY` / `CRYPTO_API_SECRET` | No — stage skipped if unset | crypto portfolio |
| `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`, `REPORT_TO` | For email stage | send_email |
| `SMTP_PORT` (587), `REPORT_FROM` (SMTP_USER) | No | send_email |

> Headless/container note: credentials must come from environment variables —
> there is no keyring (`secret-tool`) in a container.

---

## How to invoke

### Step 0 — Verify prerequisites

Run these checks before any other step. If any command fails, report the failing
check to the user and ask whether you should self-heal by running
`uv sync --all-packages`.

```bash
# Python is available via uv
uv run python --version

# Root venv exists
test -d .venv && echo "venv OK" || echo "ERROR: .venv not found"

# Required packages are importable
uv run python -c "import daily_pipeline, anthropic, markdown, yaml, common" && echo "All packages OK"

# API key is configured (required for trader + summary stages)
test -n "$ANTHROPIC_API_KEY" && echo "API key in env" || echo "ERROR: ANTHROPIC_API_KEY not set"
```

### Step 1 — Preview the run (optional)

```bash
uv run skills/daily_pipeline/scripts/run_daily.py --dry-run
```

Prints the planned stages with the thresholds from `pipeline.yaml`. Nothing executes.

### Step 2 — Run the pipeline

```bash
uv run skills/daily_pipeline/scripts/run_daily.py
```

The script prints the report path on success, e.g.:

```
skills/daily_pipeline/tmp/run_20260801/report.md
```

If SMTP is not configured, pass `--skip-email`. On stage failure the script
exits non-zero with the failing stage in the error log — re-running resumes
from that stage.

### Step 3 — Present the result

Read `manifest.json` in the run directory and report per-stage status, which
symbols the trader analysed (and which used cached verdicts), and the report
path. If email was sent, say so. Do not paste the whole report — summarise it
and point at the file.

---

## Individual stages

Each stage is also runnable standalone (all print their output path on stdout):

```bash
uv run skills/daily_pipeline/scripts/extract_tickers.py --input <analysis.json> [--top-n 5]
uv run skills/daily_pipeline/scripts/select_candidates.py --input <portfolio.json> [--min-pnl-pct 5]
uv run skills/daily_pipeline/scripts/build_report.py --analysis <a.json> --tickers <t.json> [--portfolio <p.json>] [--verdict <v.json>]...
uv run skills/daily_pipeline/scripts/send_email.py --report <report.md> [--subject "..."]
```

## Unattended runs (container)

For scheduled runs this skill ships as a one-shot container invoked by host
cron — see `docs/deployment.md`. The equivalent of Step 2 there is:

```bash
docker compose run --rm finance-pipeline
```

Steps 0–3 above still apply when running interactively from a checkout. Inside
the container all credentials come from `.env` (no keyring), and run artifacts
persist in named volumes rather than the working tree.

## Known limitations (v1)

- The crypto portfolio is fetched and recorded as an artifact but not yet
  rendered in the report, and crypto holdings are not gated into trader runs.
- The trader panel runs without a market-data context file; wiring
  `check_stock` quotes in as context is a planned improvement.
