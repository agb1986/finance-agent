# Skill: Financial News

Fetches and summarizes daily financial news.

## When to invoke

Use this skill when the user asks about:
- Today's financial or market news
- News about specific stocks, sectors, or indices
- Economic events or announcements

## Scripts

### `scripts/fetch_news.py`

Fetches the latest financial news headlines.

```bash
uv run skills/financial_news/scripts/fetch_news.py [--topic TOPIC] [--limit N]
```

**Arguments:**
- `--topic` — optional filter (e.g. `markets`, `macro`, `crypto`). Defaults to general finance.
- `--limit` — number of articles to return (default: 10)

**Output:** JSON array of articles with `title`, `source`, `url`, `published_at`, `summary` fields.

## Example invocation

> "What's happening in the markets today?"

Run `fetch_news.py` with no arguments and summarize the returned articles for the user.
