"""Tests for common.usage."""

import logging
from types import SimpleNamespace

import pytest
from common.usage import flatten, merge, record


@pytest.fixture(autouse=True)
def reset_logger():
    yield
    logging.getLogger("finance_agent").handlers.clear()


def _usage(**overrides) -> SimpleNamespace:
    fields = {
        "input_tokens": 100,
        "output_tokens": 50,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
    }
    fields.update(overrides)
    return SimpleNamespace(**fields)


class TestRecord:
    def test_captures_all_fields_keyed_by_model(self):
        assert record("claude-opus-5", _usage()) == {
            "claude-opus-5": {
                "input_tokens": 100,
                "output_tokens": 50,
                "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 0,
                "calls": 1,
            }
        }

    def test_captures_cache_fields(self):
        used = record("m", _usage(cache_read_input_tokens=900, cache_creation_input_tokens=80))
        assert used["m"]["cache_read_input_tokens"] == 900
        assert used["m"]["cache_creation_input_tokens"] == 80

    def test_missing_usage_object_yields_zeros(self):
        # The SDK omits usage on some error paths — record must not explode.
        used = record("m", None)
        assert used["m"]["input_tokens"] == 0
        assert used["m"]["calls"] == 1

    def test_none_valued_field_counts_as_zero(self):
        used = record("m", _usage(cache_read_input_tokens=None))
        assert used["m"]["cache_read_input_tokens"] == 0

    def test_non_numeric_field_counts_as_zero(self):
        used = record("m", _usage(input_tokens="lots"))
        assert used["m"]["input_tokens"] == 0


class TestMerge:
    def test_sums_same_model(self):
        merged = merge(record("m", _usage()), record("m", _usage()))
        assert merged["m"]["input_tokens"] == 200
        assert merged["m"]["calls"] == 2

    def test_keeps_models_separate(self):
        merged = merge(record("a", _usage()), record("b", _usage(input_tokens=7)))
        assert merged["a"]["input_tokens"] == 100
        assert merged["b"]["input_tokens"] == 7

    def test_ignores_none_and_empty(self):
        assert merge(None, {}, record("m", _usage()))["m"]["calls"] == 1

    def test_no_arguments_gives_empty(self):
        assert merge() == {}

    def test_does_not_mutate_inputs(self):
        original = record("m", _usage())
        merge(original, record("m", _usage()))
        assert original["m"]["input_tokens"] == 100


class TestFlatten:
    def test_sums_across_models(self):
        totals = merge(record("a", _usage()), record("b", _usage(input_tokens=25)))
        flat = flatten(totals)
        assert flat["input_tokens"] == 125
        assert flat["output_tokens"] == 100
        assert flat["calls"] == 2

    def test_empty_gives_zeros(self):
        assert flatten(None) == {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
            "calls": 0,
        }
