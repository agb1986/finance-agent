---
name: trader
version: 0.1.1
description: Runs a multi-agent investment analysis on a stock — five specialist analysts in parallel, a bull/bear debate, and a judge that scores both sides and delivers a verdict. Use when the user asks whether to buy/sell/hold a stock or wants a deep, multi-perspective investment case.
---

# Skill: Trader

Runs a three-layer multi-agent pipeline via the Anthropic SDK, with a different Claude model per stage:

| Stage | Roles | Model |
|---|---|---|
| 1. Analyst panel (parallel) | fundamental, technical, macro, sentiment, risk | `claude-sonnet-4-6` |
| 2. Bull/bear debate (2 rounds) | bull advocate, bear advocate | `claude-opus-4-8` |
| 3. Judge | impartial scorer (50-point rubric per side) | `claude-opus-4-8` |

Role prompts and model assignments live in `skills/trader/config/roles.yaml` — editable without touching code.

> **Cost note:** one full run makes 10 API calls (5× Sonnet, 4× Opus, 1× Opus for judge), measured at ~$0.16. Each stage writes its output to `tmp/`, so a failed or re-run stage never repeats earlier calls. Every artifact records its token usage — see Step 4.

## When to invoke

Use this skill when the user asks:
- "Should I buy/sell/hold <stock>?"
- For a bull vs bear case, an investment debate, or a scored verdict on a stock
- For a "deep" or "multi-angle" analysis beyond a simple quote

## Inputs

| Argument | Script | Required | Default | Description |
|---|---|---|---|---|
| `--symbol` | run_panel | Yes | — | Ticker symbol, e.g. `AMZN` |
| `--context-file` | run_panel | No | — | Path to a JSON/text file with market data to ground the panel |
| `--input` | run_debate, run_judge | Yes | — | Path to the previous stage's output file |
| `--rounds` | run_debate | No | `2` | Debate rounds (2 recommended — marginal value drops sharply after) |

---

## How to invoke

### Step 0 — Verify prerequisites

Run these checks before any other step. If any command fails, report the failing check to the user and ask whether you should self-heal by running `uv sync --all-packages`.

```bash
# Python is available via uv
uv run python --version

# Root venv exists
test -d .venv && echo "venv OK" || echo "ERROR: .venv not found"

# Required packages are importable
uv run python -c "import trader, anthropic, yaml, common" && echo "All packages OK"

# API key is configured (required — every stage calls the Anthropic API)
# Falls back to secret-tool automatically if not exported
test -n "$ANTHROPIC_API_KEY" && echo "API key in env" || secret-tool lookup service anthropic key api-key > /dev/null 2>&1 && echo "API key via secret-tool OK" || echo "ERROR: ANTHROPIC_API_KEY not set and secret-tool lookup failed"
```

If the check prints ERROR, stop and ask the user to either export `ANTHROPIC_API_KEY` or store it with:
```bash
secret-tool store --label="Anthropic API Key" service anthropic key api-key
```

---

### Step 1 (optional) — Gather market data as context

The panel produces far better briefs when grounded in real numbers. If the **check-stock** skill is available, run its quote/history steps first and pass one of its output files as context:

```bash
uv run skills/trader/scripts/run_panel.py --symbol <SYMBOL> --context-file skills/check_stock/tmp/check_stock_<SYMBOL>_<ts>.json
```

Otherwise run the panel without context (Step 2) — the analysts will rely on model knowledge and say so.

---

### Step 2 — Run the analyst panel

```bash
uv run skills/trader/scripts/run_panel.py --symbol <SYMBOL> [--context-file <path>]
```

The script prints the path to the output JSON file, e.g.:
```
skills/trader/tmp/panel_AMZN_20260610_090000.json
```

Read the file. It contains one brief per analyst role:

```json
{
  "symbol": "AMZN",
  "generated_at": "2026-06-10T09:00:00Z",
  "context_file": null,
  "panel": {
    "fundamental": "... VERDICT: buy — FCF growth",
    "technical": "... ENTRY: 195.00 ...",
    "macro": "... VERDICT: tailwind — rate-cut cycle",
    "sentiment": "... VERDICT: bullish — insider buying",
    "risk": "... MAX POSITION: 3% of portfolio — earnings volatility"
  }
}
```

---

### Step 3 — Run the bull/bear debate

```bash
uv run skills/trader/scripts/run_debate.py --input <path/to/panel_*.json>
```

The script prints the path to the output file, e.g.:
```
skills/trader/tmp/debate_AMZN_20260610_090200.json
```

It contains the panel plus a `transcript` array — round 1 argued independently from the panel data, round 2 each side rebutting the other's round 1.

---

### Step 4 — Run the judge

```bash
uv run skills/trader/scripts/run_judge.py --input <path/to/debate_*.json>
```

The script prints the path to the output file, e.g.:
```
skills/trader/tmp/verdict_AMZN_20260610_090400.json
```

The `verdict` object contains a `scorecard` (both sides scored 0–10 on evidence quality, rebuttal validity, risk-adjusted logic, internal consistency, falsifiability), `winner`, `confidence`, the strongest argument and fatal flaw for each side, `key_unresolved_question`, and a prose `verdict`.

> If the judge returned malformed JSON, the file contains `{"raw": ..., "parse_error": ...}` instead — present the raw text and note the parse failure.

Every artifact also carries a `usage` object keyed by model
(`{"claude-opus-4-8": {"input_tokens": …, "output_tokens": …, "calls": …}}`).
Each stage adds its own tokens to the total it read from the previous stage, so
`verdict_*.json` holds the token cost of the **whole** panel → debate → judge
chain — that is what the daily pipeline reads to report spend.

---

### Step 5 — Present the verdict to the user

Combine the outputs into a single response using **exactly** this format:

```markdown
## Trader verdict: <SYMBOL> — <generated_at date only>

| Dimension | Bull | Bear |
|---|---|---|
| Evidence quality | x/10 | x/10 |
| Rebuttal validity | x/10 | x/10 |
| Risk-adjusted logic | x/10 | x/10 |
| Internal consistency | x/10 | x/10 |
| Falsifiability | x/10 | x/10 |
| **Total** | **xx/50** | **xx/50** |

**Winner:** <winner> (<confidence> confidence)

**Strongest bull argument:** <strongest_bull_argument>
**Strongest bear argument:** <strongest_bear_argument>
**Bull fatal flaw:** <bull_fatal_flaw>
**Bear fatal flaw:** <bear_fatal_flaw>

**Key unresolved question:** <key_unresolved_question>

> <verdict>

---

**Generated files:**
- Panel: `<path to panel_*.json>`
- Debate: `<path to debate_*.json>`
- Verdict: `<path to verdict_*.json>`

*Multi-agent analysis generated by Claude models — not financial advice.*
```

The `key_unresolved_question` is the most actionable output — surface it prominently; it tells the user what to research next, not just who won.
