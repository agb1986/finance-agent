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
