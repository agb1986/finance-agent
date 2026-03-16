"""Tests for chart_history.py and check_crypto.charter."""

import importlib.util
import json
import logging
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_spec = importlib.util.spec_from_file_location(
    "check_crypto_chart_history", Path(__file__).parent.parent / "scripts" / "chart_history.py"
)
chart_history = importlib.util.module_from_spec(_spec)
sys.modules["check_crypto_chart_history"] = chart_history
_spec.loader.exec_module(chart_history)
from check_crypto.charter import render_ascii_chart, write_notebook  # noqa: E402


@pytest.fixture(autouse=True)
def reset_logger():
    yield
    logging.getLogger("finance_agent").handlers.clear()


SAMPLE_BARS = [
    {"date": "2026-01-02", "open": 94000.0, "high": 96000.0, "low": 93000.0, "close": 95500.0},
    {"date": "2026-01-03", "open": 95500.0, "high": 97000.0, "low": 94500.0, "close": 96200.0},
    {"date": "2026-01-04", "open": 96200.0, "high": 98000.0, "low": 95000.0, "close": 97100.0},
]

SAMPLE_DATA = {
    "coin_id": "bitcoin",
    "days": 365,
    "bars": SAMPLE_BARS,
}


# ── render_ascii_chart (library) ──────────────────────────────────────────────


class TestRenderAsciiChart:
    def test_calls_plotext(self):
        with patch("check_crypto.charter.plt") as mock_plt:
            render_ascii_chart(SAMPLE_BARS, "bitcoin")

        mock_plt.clf.assert_called_once()
        mock_plt.plot.assert_called_once()
        mock_plt.show.assert_called_once()

    def test_plots_close_prices(self):
        with patch("check_crypto.charter.plt") as mock_plt:
            render_ascii_chart(SAMPLE_BARS, "bitcoin")

        closes = [b["close"] for b in SAMPLE_BARS]
        call_args = mock_plt.plot.call_args[0][0]
        assert call_args == closes

    def test_title_contains_coin_id(self):
        with patch("check_crypto.charter.plt") as mock_plt:
            render_ascii_chart(SAMPLE_BARS, "bitcoin")

        title_arg = mock_plt.title.call_args[0][0]
        assert "BITCOIN" in title_arg


# ── write_notebook (library) ──────────────────────────────────────────────────


class TestWriteNotebook:
    def test_writes_ipynb_file(self, tmp_path):
        output = tmp_path / "chart.ipynb"
        write_notebook(SAMPLE_BARS, "bitcoin", str(output))
        assert output.exists()

    def test_output_is_valid_notebook_json(self, tmp_path):
        output = tmp_path / "chart.ipynb"
        write_notebook(SAMPLE_BARS, "bitcoin", str(output))
        nb = json.loads(output.read_text())
        assert "cells" in nb
        assert "nbformat" in nb

    def test_notebook_contains_coin_id(self, tmp_path):
        output = tmp_path / "chart.ipynb"
        write_notebook(SAMPLE_BARS, "bitcoin", str(output))
        nb = json.loads(output.read_text())
        first_cell = nb["cells"][0]
        source = (
            first_cell["source"]
            if isinstance(first_cell["source"], str)
            else "".join(first_cell["source"])
        )
        assert "bitcoin" in source.lower()


# ── main (script) ─────────────────────────────────────────────────────────────


class TestMain:
    def _history_file(self, tmp_path):
        p = tmp_path / "history_bitcoin_365d_20260316_100000.json"
        p.write_text(json.dumps(SAMPLE_DATA))
        return p

    def test_writes_notebook_and_prints_path(self, tmp_path, capsys):
        history = self._history_file(tmp_path)
        with (
            patch.object(chart_history, "TMP_DIR", tmp_path),
            patch("check_crypto_chart_history.render_ascii_chart"),
            patch("check_crypto_chart_history.write_notebook"),
            patch("sys.argv", ["chart_history.py", "--input", str(history)]),
        ):
            chart_history.main()

        captured = capsys.readouterr()
        output_path = Path(captured.out.strip())
        assert "bitcoin" in output_path.name
        assert output_path.suffix == ".ipynb"

    def test_calls_render_and_notebook(self, tmp_path):
        history = self._history_file(tmp_path)
        with (
            patch.object(chart_history, "TMP_DIR", tmp_path),
            patch("check_crypto_chart_history.render_ascii_chart") as mock_ascii,
            patch("check_crypto_chart_history.write_notebook") as mock_nb,
            patch("sys.argv", ["chart_history.py", "--input", str(history)]),
        ):
            chart_history.main()

        mock_ascii.assert_called_once_with(SAMPLE_BARS, "bitcoin")
        mock_nb.assert_called_once()

    def test_exits_when_input_not_found(self, tmp_path):
        with (
            patch.object(chart_history, "TMP_DIR", tmp_path),
            patch("sys.argv", ["chart_history.py", "--input", str(tmp_path / "missing.json")]),
        ):
            with pytest.raises(SystemExit) as exc_info:
                chart_history.main()

        assert exc_info.value.code == 1

    def test_exits_when_bars_empty(self, tmp_path):
        p = tmp_path / "history_bitcoin_365d_20260316_100000.json"
        p.write_text(json.dumps({"coin_id": "bitcoin", "days": 365, "bars": []}))
        with (
            patch.object(chart_history, "TMP_DIR", tmp_path),
            patch("sys.argv", ["chart_history.py", "--input", str(p)]),
        ):
            with pytest.raises(SystemExit) as exc_info:
                chart_history.main()

        assert exc_info.value.code == 1

    def test_input_required(self):
        with patch("sys.argv", ["chart_history.py"]):
            with pytest.raises(SystemExit) as exc_info:
                chart_history.main()

        assert exc_info.value.code == 2

    def test_exits_on_notebook_error(self, tmp_path):
        history = self._history_file(tmp_path)
        with (
            patch.object(chart_history, "TMP_DIR", tmp_path),
            patch("check_crypto_chart_history.render_ascii_chart"),
            patch("check_crypto_chart_history.write_notebook", side_effect=RuntimeError("render error")),
            patch("sys.argv", ["chart_history.py", "--input", str(history)]),
        ):
            with pytest.raises(SystemExit) as exc_info:
                chart_history.main()

        assert exc_info.value.code == 1
