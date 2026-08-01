"""Tests for scripts/select_candidates.py and daily_pipeline.candidates."""

import json
import logging
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import select_candidates as select_candidates_script
from daily_pipeline.candidates import select_candidates, symbol_from_instrument


@pytest.fixture(autouse=True)
def reset_logger():
    yield
    logging.getLogger("finance_agent").handlers.clear()


def position(ticker, name, cost, value):
    return {
        "instrument": {"ticker": ticker, "name": name},
        "walletImpact": {
            "totalCost": cost,
            "currentValue": value,
            "unrealizedProfitLoss": value - cost,
        },
    }


# ── symbol_from_instrument ────────────────────────────────────────────────────


class TestSymbolFromInstrument:
    def test_strips_exchange_suffix(self):
        assert symbol_from_instrument("AMZN_US_EQ") == "AMZN"

    def test_plain_symbol_unchanged(self):
        assert symbol_from_instrument("amzn") == "AMZN"


# ── select_candidates ─────────────────────────────────────────────────────────


class TestSelectCandidates:
    def test_selects_position_over_threshold(self):
        portfolio = {"positions": [position("AMZN_US_EQ", "Amazon", 100.0, 110.0)]}
        result = select_candidates(portfolio, min_abs_pnl_pct=5.0)
        assert result[0]["symbol"] == "AMZN"
        assert result[0]["pnl_pct"] == 10.0

    def test_negative_swing_also_selected(self):
        portfolio = {"positions": [position("SOUN_US_EQ", "SoundHound", 100.0, 90.0)]}
        result = select_candidates(portfolio, min_abs_pnl_pct=5.0)
        assert result[0]["pnl_pct"] == -10.0

    def test_below_threshold_excluded(self):
        portfolio = {"positions": [position("AMZN_US_EQ", "Amazon", 100.0, 101.0)]}
        assert select_candidates(portfolio, min_abs_pnl_pct=5.0) == []

    def test_small_position_excluded(self):
        portfolio = {"positions": [position("AMZN_US_EQ", "Amazon", 10.0, 12.0)]}
        assert select_candidates(portfolio, min_position_value=25.0) == []

    def test_zero_cost_skipped(self):
        portfolio = {"positions": [position("AMZN_US_EQ", "Amazon", 0.0, 50.0)]}
        assert select_candidates(portfolio) == []

    def test_sorted_by_abs_pnl_and_capped(self):
        portfolio = {
            "positions": [
                position("A_US_EQ", "A", 100.0, 106.0),
                position("B_US_EQ", "B", 100.0, 80.0),
                position("C_US_EQ", "C", 100.0, 110.0),
            ]
        }
        result = select_candidates(portfolio, max_candidates=2)
        assert [c["symbol"] for c in result] == ["B", "C"]

    def test_empty_portfolio(self):
        assert select_candidates({}) == []


# ── script main ───────────────────────────────────────────────────────────────


class TestMain:
    def test_writes_output_and_prints_path(self, tmp_path, capsys):
        portfolio_path = tmp_path / "portfolio.json"
        portfolio_path.write_text(
            json.dumps({"positions": [position("AMZN_US_EQ", "Amazon", 100.0, 110.0)]})
        )
        argv = ["select_candidates.py", "--input", str(portfolio_path)]
        with (
            patch.object(select_candidates_script, "TMP_DIR", tmp_path / "out"),
            patch.object(sys, "argv", argv),
        ):
            select_candidates_script.main()

        output_path = Path(capsys.readouterr().out.strip())
        results = json.loads(output_path.read_text())
        assert results[0]["symbol"] == "AMZN"

    def test_missing_input_exits_nonzero(self, tmp_path):
        argv = ["select_candidates.py", "--input", str(tmp_path / "nope.json")]
        with patch.object(sys, "argv", argv), pytest.raises(SystemExit) as excinfo:
            select_candidates_script.main()
        assert excinfo.value.code == 1
