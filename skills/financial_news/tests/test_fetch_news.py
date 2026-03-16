"""
Tests for skills/financial_news/scripts/fetch_news.py and financial_news.fetcher.
"""

import json
import logging
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import fetch_news
from financial_news.fetcher import fetch_feed, strip_html


@pytest.fixture(autouse=True)
def reset_logger():
    yield
    logging.getLogger("finance_agent").handlers.clear()


# ── helpers ───────────────────────────────────────────────────────────────────

CUTOFF = time.gmtime(1_000_000)
PAST = time.gmtime(999_999)
FUTURE = time.gmtime(9_999_999_999)


def _make_entry(title: str = "Test", published: time.struct_time = FUTURE, no_date: bool = False):
    pub = None if no_date else published
    entry = MagicMock()
    entry.get = lambda key, default="": {
        "title": title,
        "summary": f"<b>{title} summary</b>",
        "link": "https://example.com/article",
        "published_parsed": pub,
    }.get(key, default)
    return entry


def _make_feed(entries: list | None = None, bozo: bool = False):
    feed = MagicMock()
    feed.bozo = bozo
    feed.entries = entries or []
    feed.bozo_exception = Exception("parse error")
    return feed


# ── strip_html ────────────────────────────────────────────────────────────────


class TestStripHtml:
    def test_empty_string(self):
        assert strip_html("") == ""

    def test_none_returns_empty(self):
        assert strip_html(None) == ""

    def test_plain_text_unchanged(self):
        assert strip_html("hello world") == "hello world"

    def test_basic_tags_stripped(self):
        assert strip_html("<b>Hello</b><b>world</b>") == "Hello world"

    def test_nested_tags(self):
        result = strip_html("<div><p>First</p><p>Second</p></div>")
        assert "First" in result
        assert "Second" in result


# ── fetch_feed ────────────────────────────────────────────────────────────────


class TestFetchFeed:
    def test_bozo_no_entries_returns_empty(self):
        with patch("feedparser.parse", return_value=_make_feed(bozo=True)):
            result = fetch_feed("Feed", "http://x.com", CUTOFF)
        assert result == []

    def test_bozo_with_entries_still_processes(self):
        with patch("feedparser.parse", return_value=_make_feed(bozo=True, entries=[_make_entry()])):
            result = fetch_feed("Feed", "http://x.com", CUTOFF)
        assert len(result) == 1

    def test_entry_before_cutoff_excluded(self):
        with patch(
            "feedparser.parse", return_value=_make_feed(entries=[_make_entry(published=PAST)])
        ):
            result = fetch_feed("Feed", "http://x.com", CUTOFF)
        assert result == []

    def test_entry_with_no_date_excluded(self):
        with patch(
            "feedparser.parse", return_value=_make_feed(entries=[_make_entry(no_date=True)])
        ):
            result = fetch_feed("Feed", "http://x.com", CUTOFF)
        assert result == []

    def test_fresh_entry_included_with_correct_fields(self):
        with patch(
            "feedparser.parse", return_value=_make_feed(entries=[_make_entry(title="Fresh")])
        ):
            result = fetch_feed("TestFeed", "http://x.com", CUTOFF)
        assert len(result) == 1
        r = result[0]
        assert r["title"] == "Fresh"
        assert r["source"] == "TestFeed"
        assert r["url"] == "https://example.com/article"
        assert "Fresh summary" in r["summary"]
        assert "published_at" in r

    def test_empty_feed_returns_empty(self):
        with patch("feedparser.parse", return_value=_make_feed()):
            result = fetch_feed("Feed", "http://x.com", CUTOFF)
        assert result == []

    def test_mixed_dates_only_fresh_returned(self):
        fresh = _make_entry(title="New")
        old = _make_entry(title="Old", published=PAST)
        with patch("feedparser.parse", return_value=_make_feed(entries=[fresh, old])):
            result = fetch_feed("Feed", "http://x.com", CUTOFF)
        assert len(result) == 1
        assert result[0]["title"] == "New"

    def test_multiple_fresh_entries_all_returned(self):
        entries = [_make_entry(title=f"Article {i}") for i in range(3)]
        with patch("feedparser.parse", return_value=_make_feed(entries=entries)):
            result = fetch_feed("Feed", "http://x.com", CUTOFF)
        assert len(result) == 3


# ── main ──────────────────────────────────────────────────────────────────────

_SINGLE_FEED = {"TestFeed": "http://x.com/feed"}


class TestMain:
    def _run(self, args: list[str], entries: list, tmp_path: Path, capsys):
        feed = _make_feed(entries=entries)
        with (
            patch("sys.argv", ["fetch_news.py"] + args),
            patch.object(fetch_news, "TMP_DIR", tmp_path),
            patch.object(fetch_news, "FEEDS", _SINGLE_FEED),
            patch("feedparser.parse", return_value=feed),
        ):
            fetch_news.main()
        return capsys.readouterr()

    def test_writes_json_file(self, tmp_path, capsys):
        self._run([], [_make_entry(title="Article 1")], tmp_path, capsys)
        files = list(tmp_path.iterdir())
        assert len(files) == 1
        data = json.loads(files[0].read_text())
        assert len(data) == 1
        assert data[0]["title"] == "Article 1"

    def test_prints_output_path_to_stdout(self, tmp_path, capsys):
        cap = self._run([], [], tmp_path, capsys)
        assert str(tmp_path) in cap.out
        assert cap.out.strip().endswith(".json")

    def test_empty_feeds_writes_empty_array(self, tmp_path, capsys):
        self._run([], [], tmp_path, capsys)
        files = list(tmp_path.iterdir())
        data = json.loads(files[0].read_text())
        assert data == []

    def test_articles_sorted_newest_first(self, tmp_path, capsys):
        t_old = time.gmtime(9_000_000_000)
        t_new = time.gmtime(9_000_000_100)
        entries = [
            _make_entry(title="Old", published=t_old),
            _make_entry(title="New", published=t_new),
        ]
        self._run([], entries, tmp_path, capsys)
        data = json.loads(list(tmp_path.iterdir())[0].read_text())
        assert data[0]["title"] == "New"
        assert data[1]["title"] == "Old"

    def test_creates_tmp_dir_if_missing(self, tmp_path, capsys):
        nested = tmp_path / "subdir"
        assert not nested.exists()
        with (
            patch("sys.argv", ["fetch_news.py"]),
            patch.object(fetch_news, "TMP_DIR", nested),
            patch.object(fetch_news, "FEEDS", _SINGLE_FEED),
            patch("feedparser.parse", return_value=_make_feed()),
        ):
            fetch_news.main()
        assert nested.exists()

    def test_custom_hours_arg(self, tmp_path, capsys):
        self._run(["--hours", "48"], [], tmp_path, capsys)
        assert len(list(tmp_path.iterdir())) == 1

    def test_debug_flag_accepted(self, tmp_path, capsys):
        self._run(["--debug"], [], tmp_path, capsys)
        assert len(list(tmp_path.iterdir())) == 1

    def test_output_is_valid_json(self, tmp_path, capsys):
        entries = [_make_entry(title=f"Story {i}") for i in range(5)]
        self._run([], entries, tmp_path, capsys)
        content = list(tmp_path.iterdir())[0].read_text()
        data = json.loads(content)
        assert isinstance(data, list)
        assert all({"title", "url", "source", "published_at", "summary"} <= d.keys() for d in data)

    def test_feed_error_does_not_abort(self, tmp_path, capsys):
        with (
            patch("sys.argv", ["fetch_news.py"]),
            patch.object(fetch_news, "TMP_DIR", tmp_path),
            patch.object(fetch_news, "FEEDS", _SINGLE_FEED),
            patch("feedparser.parse", return_value=_make_feed(bozo=True, entries=[])),
        ):
            fetch_news.main()
        assert len(list(tmp_path.iterdir())) == 1
