"""
Charting logic for cryptocurrency history data.
"""

import json
from pathlib import Path

import nbformat
import plotext as plt
from common.logger import get_logger

logger = get_logger()


def render_ascii_chart(bars: list[dict], coin_id: str) -> None:
    """Render an ASCII line chart of closing prices to the console.

    Args:
        bars: List of OHLCV bar dicts with 'date' and 'close' keys.
        coin_id: Coin identifier, used in the chart title.
    """
    closes = [b["close"] for b in bars]
    dates = [b["date"] for b in bars]

    plt.clf()
    plt.plot(closes, label="Close (USD)")
    plt.title(f"{coin_id.upper()} — Closing Price (USD)")
    plt.xlabel("Days")
    plt.ylabel("USD")
    step = max(1, len(dates) // 8)
    plt.xticks(list(range(0, len(dates), step)), dates[::step])
    plt.show()
    logger.debug(f"rendered ASCII chart for {coin_id!r} ({len(bars)} bars)")


def write_notebook(bars: list[dict], coin_id: str, output_path: str) -> None:
    """Write a Jupyter notebook with candlestick, line, and OHLC charts.

    Args:
        bars: List of OHLC bar dicts.
        coin_id: Coin identifier.
        output_path: Destination path for the .ipynb file.
    """
    code = f"""\
import pandas as pd
import mplfinance as mpf

data = {json.dumps(bars)}
df = pd.DataFrame(data)
df['date'] = pd.to_datetime(df['date'])
df = df.set_index('date')
df.columns = [c.capitalize() for c in df.columns]

mpf.plot(df, type='candle', title='{coin_id.upper()} — Candlestick', style='charles', volume=False)
mpf.plot(df, type='line',   title='{coin_id.upper()} — Line',        style='charles', volume=False)
mpf.plot(df, type='ohlc',   title='{coin_id.upper()} — OHLC',        style='charles', volume=False)
"""

    nb = nbformat.v4.new_notebook()
    nb.cells = [nbformat.v4.new_code_cell(code)]
    Path(output_path).write_text(nbformat.writes(nb))
    logger.debug(f"wrote notebook for {coin_id!r} to {output_path}")
