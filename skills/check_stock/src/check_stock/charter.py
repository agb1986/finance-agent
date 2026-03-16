"""
Stock chart generation.

Provides two outputs from a history data dict:
  - chart_to_notebook: writes a Jupyter notebook with candlestick, line, and OHLC charts
  - chart_to_console:  renders an ASCII line chart to the terminal via plotext
"""

import base64
import io
from pathlib import Path

import matplotlib.pyplot as plt_mpl
import mplfinance as mpf
import nbformat as nbf
import pandas as pd
import plotext as ptx
from common.logger import get_logger

CHART_TYPES = [
    ("candle", "Candlestick"),
    ("line", "Line (Close)"),
    ("ohlc", "OHLC Bar"),
]


def find_latest_history(tmp_dir: Path) -> Path:
    """Return the most recently created history JSON in tmp_dir."""
    files = sorted(tmp_dir.glob("history_*.json"), reverse=True)
    if not files:
        raise FileNotFoundError(f"No history_*.json found in {tmp_dir}")
    return files[0]


def _to_dataframe(data: dict) -> pd.DataFrame:
    """Convert history bars to a mplfinance-compatible DataFrame."""
    df = pd.DataFrame(data["bars"])
    df["date"] = pd.to_datetime(df["date"], utc=True)
    df = df.set_index("date")
    df.columns = [c.capitalize() for c in df.columns]
    return df


def _fig_to_base64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=150)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def chart_to_notebook(data: dict, output_path: Path) -> None:
    """
    Generate a Jupyter notebook with candlestick, line, and OHLC charts.

    Charts are pre-rendered so they display immediately when the notebook is opened.

    Args:
        data:        History dict as returned by fetch_history().
        output_path: Where to write the .ipynb file.
    """
    logger = get_logger()
    symbol = data["symbol"]
    period = data["period"]

    logger.debug(f"chart_to_notebook: symbol={symbol!r}, period={period!r}")

    df = _to_dataframe(data)

    nb = nbf.v4.new_notebook()
    cells = [nbf.v4.new_markdown_cell(f"# {symbol} — Price History ({period})")]

    for chart_type, title in CHART_TYPES:
        logger.debug(f"rendering {title} chart")

        fig, _ = mpf.plot(
            df,
            type=chart_type,
            title=f"{symbol} — {title} ({period})",
            ylabel="Price (USD)",
            volume=True,
            returnfig=True,
            figsize=(12, 6),
            style="charles",
        )
        img_b64 = _fig_to_base64(fig)
        plt_mpl.close(fig)

        cells.append(nbf.v4.new_markdown_cell(f"## {title}"))

        code = (
            f"import mplfinance as mpf\n"
            f"mpf.plot(df, type='{chart_type}', "
            f"title='{symbol} — {title} ({period})', "
            f"ylabel='Price (USD)', volume=True, figsize=(12, 6), style='charles')"
        )
        cell = nbf.v4.new_code_cell(code)
        cell.outputs = [
            nbf.v4.new_output(
                output_type="display_data",
                data={"image/png": img_b64, "text/plain": [f"<{title} Chart>"]},
            )
        ]
        cells.append(cell)

    nb.cells = cells
    output_path.write_text(nbf.writes(nb))
    logger.debug(f"notebook written to {output_path}")


def chart_to_console(data: dict) -> None:
    """
    Render an ASCII line chart of closing prices to the terminal.

    Args:
        data: History dict as returned by fetch_history().
    """
    logger = get_logger()
    symbol = data["symbol"]
    period = data["period"]
    bars = data["bars"]

    logger.debug(f"chart_to_console: symbol={symbol!r}, bars={len(bars)}")

    dates = [b["date"] for b in bars]
    closes = [b["close"] for b in bars]

    # Show a readable number of x-axis labels
    step = max(1, len(dates) // 8)
    x_labels = {i: dates[i] for i in range(0, len(dates), step)}

    ptx.clear_figure()
    ptx.plot(closes, marker="braille")
    ptx.title(f"{symbol} — Close Price ({period})")
    ptx.xlabel("Date")
    ptx.ylabel("Price")
    ptx.xticks(list(x_labels.keys()), list(x_labels.values()))
    ptx.show()
