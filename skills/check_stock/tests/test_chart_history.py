"""Tests for chart_history.py and check_stock.charter."""

import importlib.util
import json
import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_spec = importlib.util.spec_from_file_location(
    "check_stock_chart_history", Path(__file__).parent.parent / "scripts" / "chart_history.py"
)
chart_history = importlib.util.module_from_spec(_spec)
sys.modules["check_stock_chart_history"] = chart_history
_spec.loader.exec_module(chart_history)
from check_stock.charter import (  # noqa: E402
    CHART_TYPES,
    chart_to_console,
    chart_to_notebook,
    find_latest_history,
)


@pytest.fixture(autouse=True)
def reset_logger():
    yield
    logging.getLogger("finance_agent").handlers.clear()


SAMPLE_DATA = {
    "symbol": "AMZN",
    "market": "NASDAQ",
    "period": "1mo",
    "fetched_at": "2026-03-16T10:00:00Z",
    "bars": [
        {
            "date": "2026-01-02",
            "open": 200.0,
            "high": 210.0,
            "low": 198.0,
            "close": 207.5,
            "volume": 30_000_000,
        },
        {
            "date": "2026-01-03",
            "open": 207.5,
            "high": 215.0,
            "low": 205.0,
            "close": 212.0,
            "volume": 28_000_000,
        },
        {
            "date": "2026-01-04",
            "open": 212.0,
            "high": 214.0,
            "low": 208.0,
            "close": 209.0,
            "volume": 25_000_000,
        },
    ],
}


# ── find_latest_history ───────────────────────────────────────────────────────


class TestFindLatestHistory:
    def test_returns_most_recent_file(self, tmp_path):
        (tmp_path / "history_AMZN_1mo_20260315_120000.json").touch()
        (tmp_path / "history_AMZN_1mo_20260315_140000.json").touch()
        result = find_latest_history(tmp_path)
        assert result.name == "history_AMZN_1mo_20260315_140000.json"

    def test_raises_when_no_files(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="No history_"):
            find_latest_history(tmp_path)


# ── chart_to_console ──────────────────────────────────────────────────────────


class TestChartToConsole:
    def test_calls_plotext(self):
        with patch("check_stock.charter.ptx") as mock_ptx:
            chart_to_console(SAMPLE_DATA)

        mock_ptx.clear_figure.assert_called_once()
        mock_ptx.plot.assert_called_once()
        mock_ptx.show.assert_called_once()

    def test_plots_close_prices(self):
        with patch("check_stock.charter.ptx") as mock_ptx:
            chart_to_console(SAMPLE_DATA)

        closes = [b["close"] for b in SAMPLE_DATA["bars"]]
        mock_ptx.plot.assert_called_once_with(closes, marker="braille")

    def test_sets_title_with_symbol_and_period(self):
        with patch("check_stock.charter.ptx") as mock_ptx:
            chart_to_console(SAMPLE_DATA)

        title_arg = mock_ptx.title.call_args[0][0]
        assert "AMZN" in title_arg
        assert "1mo" in title_arg


# ── chart_to_notebook ─────────────────────────────────────────────────────────


class TestChartToNotebook:
    def _mock_mpf(self):
        mock_fig = MagicMock()
        mock_fig.savefig = lambda buf, **kw: buf.write(b"PNG_DATA")
        mock_axes = MagicMock()
        mock_mpf = MagicMock()
        mock_mpf.plot.return_value = (mock_fig, mock_axes)
        return mock_mpf

    def test_writes_ipynb_file(self, tmp_path):
        output = tmp_path / "chart.ipynb"
        with (
            patch("check_stock.charter.mpf", self._mock_mpf()),
            patch("check_stock.charter.plt_mpl"),
        ):
            chart_to_notebook(SAMPLE_DATA, output)

        assert output.exists()

    def test_output_is_valid_json(self, tmp_path):
        output = tmp_path / "chart.ipynb"
        with (
            patch("check_stock.charter.mpf", self._mock_mpf()),
            patch("check_stock.charter.plt_mpl"),
        ):
            chart_to_notebook(SAMPLE_DATA, output)

        nb = json.loads(output.read_text())
        assert "cells" in nb
        assert "nbformat" in nb

    def test_renders_all_three_chart_types(self, tmp_path):
        output = tmp_path / "chart.ipynb"
        mock_mpf = self._mock_mpf()
        with (
            patch("check_stock.charter.mpf", mock_mpf),
            patch("check_stock.charter.plt_mpl"),
        ):
            chart_to_notebook(SAMPLE_DATA, output)

        assert mock_mpf.plot.call_count == len(CHART_TYPES)
        called_types = [c.kwargs["type"] for c in mock_mpf.plot.call_args_list]
        assert set(called_types) == {"candle", "line", "ohlc"}

    def test_notebook_contains_symbol_in_title(self, tmp_path):
        output = tmp_path / "chart.ipynb"
        with (
            patch("check_stock.charter.mpf", self._mock_mpf()),
            patch("check_stock.charter.plt_mpl"),
        ):
            chart_to_notebook(SAMPLE_DATA, output)

        nb = json.loads(output.read_text())
        first_cell = nb["cells"][0]
        source = (
            first_cell["source"]
            if isinstance(first_cell["source"], str)
            else "".join(first_cell["source"])
        )
        assert "AMZN" in source

    def test_closes_figures_after_render(self, tmp_path):
        output = tmp_path / "chart.ipynb"
        mock_plt = MagicMock()
        with (
            patch("check_stock.charter.mpf", self._mock_mpf()),
            patch("check_stock.charter.plt_mpl", mock_plt),
        ):
            chart_to_notebook(SAMPLE_DATA, output)

        assert mock_plt.close.call_count == len(CHART_TYPES)


# ── main (script) ─────────────────────────────────────────────────────────────


class TestMain:
    def _history_file(self, tmp_path):
        p = tmp_path / "history_AMZN_1mo_20260316_100000.json"
        p.write_text(json.dumps(SAMPLE_DATA))
        return p

    def test_writes_notebook_and_prints_path(self, tmp_path, capsys):
        history = self._history_file(tmp_path)
        with (
            patch.object(chart_history, "TMP_DIR", tmp_path),
            patch("check_stock_chart_history.chart_to_console"),
            patch("check_stock_chart_history.chart_to_notebook"),
            patch("sys.argv", ["chart_history.py", "--input", str(history)]),
        ):
            chart_history.main()

        captured = capsys.readouterr()
        output_path = Path(captured.out.strip())
        assert "AMZN" in output_path.name
        assert output_path.suffix == ".ipynb"

    def test_defaults_to_most_recent_history(self, tmp_path):
        history = self._history_file(tmp_path)
        with (
            patch.object(chart_history, "TMP_DIR", tmp_path),
            patch("check_stock_chart_history.chart_to_console"),
            patch("check_stock_chart_history.chart_to_notebook"),
            patch("check_stock_chart_history.find_latest_history", return_value=history) as mock_find,
            patch("sys.argv", ["chart_history.py"]),
        ):
            chart_history.main()

        mock_find.assert_called_once_with(tmp_path)

    def test_exits_when_no_history_file(self, tmp_path):
        with (
            patch.object(chart_history, "TMP_DIR", tmp_path),
            patch("sys.argv", ["chart_history.py"]),
        ):
            with pytest.raises(SystemExit) as exc_info:
                chart_history.main()

        assert exc_info.value.code == 1

    def test_calls_console_and_notebook(self, tmp_path):
        history = self._history_file(tmp_path)
        with (
            patch.object(chart_history, "TMP_DIR", tmp_path),
            patch("check_stock_chart_history.chart_to_console") as mock_console,
            patch("check_stock_chart_history.chart_to_notebook") as mock_nb,
            patch("sys.argv", ["chart_history.py", "--input", str(history)]),
        ):
            chart_history.main()

        mock_console.assert_called_once_with(SAMPLE_DATA)
        mock_nb.assert_called_once()

    def test_exits_on_notebook_error(self, tmp_path):
        history = self._history_file(tmp_path)
        with (
            patch.object(chart_history, "TMP_DIR", tmp_path),
            patch("check_stock_chart_history.chart_to_console"),
            patch("check_stock_chart_history.chart_to_notebook", side_effect=RuntimeError("render error")),
            patch("sys.argv", ["chart_history.py", "--input", str(history)]),
        ):
            with pytest.raises(SystemExit) as exc_info:
                chart_history.main()

        assert exc_info.value.code == 1
