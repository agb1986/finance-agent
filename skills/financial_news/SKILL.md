---
name: financial-news
description: Fetches and summarises financial news from RSS feeds. Use when the user asks about today's market news, recent market movements, crypto news, earnings reports, or stock picks.
---

# Skill: Financial News

Fetches and summarises daily financial news from multiple RSS feeds.

## When to invoke

Use this skill when the user asks about:
- Today's financial or market news
- Recent market movements or economic events
- Crypto news or opinions
- Earnings reports or stock picks

## How to invoke

### Step 1 — Run the fetch script

```bash
uv run skills/financial_news/scripts/fetch_news.py
```

Optional arguments:
- `--hours N` — look back N hours instead of the default 24

The script will print the path to the output file on stdout, e.g.:
```
skills/financial_news/tmp/news_results_20260315_143000.json
```

### Step 2 — Read the output file

Read the file path returned in Step 1. It contains a JSON array of articles sorted newest-first:

```json
[
  {
    "title": "string",
    "summary": "string",
    "url": "string",
    "published_at": "2026-03-15T14:30:00Z",
    "source": "string"
  }
]
```

### Step 3 — Summarise for the user

Present a concise summary of the most relevant articles. Group by theme where appropriate (e.g. markets, crypto, earnings). Include URLs so the user can read further.

---

## Analysing and ranking articles

### Step 1 — Configure keywords

Edit `skills/financial_news/keywords.json` to define the topics you care about:

```json
{
  "keywords": ["bitcoin", "ETF", "interest rates", "earnings", "Fed"]
}
```

Keywords are matched case-insensitively against each article's title and summary.

### Step 2 — Run the analysis script

```bash
uv run skills/financial_news/scripts/analyze_news.py
```

Optional arguments:
- `--input path/to/news_results.json` — analyse a specific fetch result instead of the most recent
- `--config path/to/keywords.json` — use an alternative keywords config

The script will print the path to the output file on stdout, e.g.:
```
skills/financial_news/tmp/analysis_20260315_143000.json
```

### Step 3 — Read the output file

Read the file path returned in Step 2. It contains the same article array as the fetch output, sorted by `semantic_score` descending, with three additional fields per article:

```json
[
  {
    "title": "string",
    "summary": "string",
    "url": "string",
    "published_at": "2026-03-15T14:30:00Z",
    "source": "string",
    "keyword_score": 0.8,
    "semantic_score": 0.91,
    "matched_keywords": ["bitcoin", "etf"],
    "rank": 1
  }
]
```

| Field | Description |
|---|---|
| `keyword_score` | Fraction of configured keywords found in the article text (0.0–1.0) |
| `semantic_score` | Cosine similarity between the article and keyword query using `all-MiniLM-L6-v2` (0.0–1.0) |
| `matched_keywords` | List of keywords that were literally matched |
| `rank` | Position after sorting by `semantic_score` descending |

### Step 4 — Summarise for the user

Present results using **exactly** the following format. Do not deviate from this structure.

---

Split articles into two groups based on their scores:

**Group 1 — Top matches** (`keyword_score > 0` AND `semantic_score >= 0.45`)
**Group 2 — Semantically relevant** (`keyword_score == 0` AND `semantic_score >= 0.40`)

Only include articles that qualify for one of these groups. Do not list articles below the thresholds.

For each article render:

```
**#<rank> — <title>**
*<source>* · semantic: <semantic_score> · keyword: <keyword_score> (<matched_keywords, comma separated, or blank if none>)
> <summary, or omit the > line entirely if summary is empty>
> [Read more](<url>)
```

Then after all articles, always include an **Observation** paragraph commenting on:
- The spread of semantic scores (tight clustering vs wide separation)
- What the keyword match rate suggests about keyword specificity
- A concrete suggestion for improving the keywords config if relevant

The full output template:

```markdown
### Top matches (high semantic + keyword score)

**#N — Title**
*Source* · semantic: 0.00 · keyword: 0.00 (`keyword1`, `keyword2`)
> Summary text.
> [Read more](url)

---

### Semantically relevant (no keyword match, but thematically close)

**#N — Title**
*Source* · semantic: 0.00 · keyword: 0.00
> Summary text.
> [Read more](url)

---

**Observation:** ...
```

If no articles qualify for a group, omit that group's heading entirely.
If both groups are empty, tell the user no articles matched and suggest reviewing the keywords config.

---

## Sources

| Source | Coverage |
|--------|----------|
| MarketWatch Top Stories | General markets |
| Yahoo Finance - Markets | S&P 500, Dow, Nasdaq news |
| CNBC Top News | Broad financial & economic news |
| Investing.com - Crypto News | Cryptocurrency news |
| Investing.com - Crypto Opinion | Cryptocurrency analysis |
| Investing.com - Investing Ideas | Investment ideas & strategies |
| Investing.com - Earnings Reports & Whispers | Upcoming & recent earnings |
| Investing.com - Earnings Call Transcripts | Earnings call summaries |
| Investing.com - Stock Picks | Analyst stock recommendations |
| The Motley Fool | Investing commentary & analysis |
