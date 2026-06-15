"""Tests for run_debate.py and trader.debate."""

import importlib.util
import json
import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from trader.debate import build_base_prompt, run_debate

_spec = importlib.util.spec_from_file_location(
    "trader_run_debate", Path(__file__).parent.parent / "scripts" / "run_debate.py"
)
run_debate_script = importlib.util.module_from_spec(_spec)
sys.modules["trader_run_debate"] = run_debate_script
_spec.loader.exec_module(run_debate_script)


@pytest.fixture(autouse=True)
def reset_logger():
    yield
    logging.getLogger("finance_agent").handlers.clear()


SAMPLE_CONFIG = {
    "models": {
        "panel": "claude-sonnet-4-6",
        "debate": "claude-opus-4-8",
        "judge": "claude-opus-4-8",
    },
    "max_tokens": {"panel": 1024, "debate": 2048, "judge": 2048},
    "panel": {"fundamental": "f", "risk": "r"},
    "debate": {"bull": "You are the bull.", "bear": "You are the bear."},
    "judge": "You are the judge.",
}

SAMPLE_PANEL = {"fundamental": "strong earnings", "risk": "cap at 3%"}


def _scripted_client(replies: dict[str, list[str]]) -> MagicMock:
    """Client whose responses depend on the system prompt (bull vs bear)."""
    counters = {side: iter(texts) for side, texts in replies.items()}

    def _create(**kwargs):
        side = "bull" if kwargs["system"] == SAMPLE_CONFIG["debate"]["bull"] else "bear"
        block = MagicMock()
        block.type = "text"
        block.text = next(counters[side])
        response = MagicMock()
        response.content = [block]
        return response

    client = MagicMock()
    client.messages.create.side_effect = _create
    return client


# ── build_base_prompt / run_debate (library) ──────────────────────────────────


class TestBuildBasePrompt:
    def test_includes_symbol_and_all_briefs(self):
        prompt = build_base_prompt("AMZN", SAMPLE_PANEL)
        assert prompt.startswith("Stock: AMZN")
        assert "FUNDAMENTAL:\nstrong earnings" in prompt
        assert "RISK:\ncap at 3%" in prompt


class TestRunDebate:
    def test_two_rounds_produce_four_entries(self):
        client = _scripted_client({"bull": ["b1", "b2"], "bear": ["r1", "r2"]})

        transcript = run_debate(client, SAMPLE_CONFIG, "AMZN", SAMPLE_PANEL)

        assert [(e["round"], e["side"], e["argument"]) for e in transcript] == [
            (1, "bull", "b1"),
            (1, "bear", "r1"),
            (2, "bull", "b2"),
            (2, "bear", "r2"),
        ]

    def test_round_one_is_independent(self):
        client = _scripted_client({"bull": ["b1", "b2"], "bear": ["r1", "r2"]})

        run_debate(client, SAMPLE_CONFIG, "AMZN", SAMPLE_PANEL)

        base = build_base_prompt("AMZN", SAMPLE_PANEL)
        round_one = client.messages.create.call_args_list[:2]
        for call in round_one:
            assert call.kwargs["messages"][0]["content"] == base

    def test_round_two_rebuts_opponents_round_one(self):
        client = _scripted_client({"bull": ["b1", "b2"], "bear": ["r1", "r2"]})

        run_debate(client, SAMPLE_CONFIG, "AMZN", SAMPLE_PANEL)

        calls = client.messages.create.call_args_list
        bull_r2 = calls[2].kwargs["messages"][0]["content"]
        bear_r2 = calls[3].kwargs["messages"][0]["content"]
        assert "BEAR TO REBUT:\nr1" in bull_r2
        assert "BULL TO REBUT:\nb1" in bear_r2

    def test_uses_debate_model(self):
        client = _scripted_client({"bull": ["b1", "b2"], "bear": ["r1", "r2"]})

        run_debate(client, SAMPLE_CONFIG, "AMZN", SAMPLE_PANEL)

        for call in client.messages.create.call_args_list:
            assert call.kwargs["model"] == "claude-opus-4-8"

    def test_single_round(self):
        client = _scripted_client({"bull": ["b1"], "bear": ["r1"]})

        transcript = run_debate(client, SAMPLE_CONFIG, "AMZN", SAMPLE_PANEL, rounds=1)

        assert len(transcript) == 2
        assert client.messages.create.call_count == 2


# ── main (script) ─────────────────────────────────────────────────────────────

SAMPLE_TRANSCRIPT = [
    {"round": 1, "side": "bull", "argument": "b1"},
    {"round": 1, "side": "bear", "argument": "r1"},
]


class TestMain:
    def _panel_file(self, tmp_path: Path) -> Path:
        panel_file = tmp_path / "panel_AMZN_x.json"
        panel_file.write_text(json.dumps({"symbol": "AMZN", "panel": SAMPLE_PANEL}))
        return panel_file

    def _patches(self, tmp_path, **overrides):
        defaults = {
            "get_client": MagicMock(),
            "load_config": MagicMock(return_value=SAMPLE_CONFIG),
            "run_debate": MagicMock(return_value=SAMPLE_TRANSCRIPT),
        }
        defaults.update(overrides)
        return (
            patch.object(run_debate_script, "TMP_DIR", tmp_path / "out"),
            patch.object(run_debate_script, "get_client", defaults["get_client"]),
            patch.object(run_debate_script, "load_config", defaults["load_config"]),
            patch.object(run_debate_script, "run_debate", defaults["run_debate"]),
        )

    def test_writes_json_and_prints_path(self, tmp_path, capsys):
        panel_file = self._panel_file(tmp_path)
        p1, p2, p3, p4 = self._patches(tmp_path)
        with p1, p2, p3, p4:
            with patch("sys.argv", ["run_debate.py", "--input", str(panel_file)]):
                run_debate_script.main()

        output_path = Path(capsys.readouterr().out.strip())
        assert output_path.exists()
        assert "debate_AMZN_" in output_path.name

        data = json.loads(output_path.read_text())
        assert data["symbol"] == "AMZN"
        assert data["rounds"] == 2
        assert data["panel"] == SAMPLE_PANEL
        assert data["transcript"] == SAMPLE_TRANSCRIPT

    def test_passes_rounds_to_debate(self, tmp_path):
        panel_file = self._panel_file(tmp_path)
        mock_run = MagicMock(return_value=SAMPLE_TRANSCRIPT)
        p1, p2, p3, p4 = self._patches(tmp_path, run_debate=mock_run)
        with p1, p2, p3, p4:
            argv = ["run_debate.py", "--input", str(panel_file), "--rounds", "3"]
            with patch("sys.argv", argv):
                run_debate_script.main()

        assert mock_run.call_args.args[4] == 3

    def test_exits_on_invalid_rounds(self, tmp_path):
        panel_file = self._panel_file(tmp_path)
        p1, p2, p3, p4 = self._patches(tmp_path)
        with p1, p2, p3, p4:
            argv = ["run_debate.py", "--input", str(panel_file), "--rounds", "0"]
            with patch("sys.argv", argv):
                with pytest.raises(SystemExit) as exc_info:
                    run_debate_script.main()

        assert exc_info.value.code == 1

    def test_exits_on_missing_input(self, tmp_path):
        p1, p2, p3, p4 = self._patches(tmp_path)
        with p1, p2, p3, p4:
            with patch("sys.argv", ["run_debate.py", "--input", "/nope/missing.json"]):
                with pytest.raises(SystemExit) as exc_info:
                    run_debate_script.main()

        assert exc_info.value.code == 1

    def test_exits_on_malformed_input(self, tmp_path):
        bad_file = tmp_path / "bad.json"
        bad_file.write_text('{"symbol": "AMZN"}')  # no "panel" key
        p1, p2, p3, p4 = self._patches(tmp_path)
        with p1, p2, p3, p4:
            with patch("sys.argv", ["run_debate.py", "--input", str(bad_file)]):
                with pytest.raises(SystemExit) as exc_info:
                    run_debate_script.main()

        assert exc_info.value.code == 1

    def test_exits_on_debate_error(self, tmp_path):
        panel_file = self._panel_file(tmp_path)
        mock_run = MagicMock(side_effect=RuntimeError("API error"))
        p1, p2, p3, p4 = self._patches(tmp_path, run_debate=mock_run)
        with p1, p2, p3, p4:
            with patch("sys.argv", ["run_debate.py", "--input", str(panel_file)]):
                with pytest.raises(SystemExit) as exc_info:
                    run_debate_script.main()

        assert exc_info.value.code == 1

    def test_input_required(self):
        with patch("sys.argv", ["run_debate.py"]):
            with pytest.raises(SystemExit) as exc_info:
                run_debate_script.main()

        assert exc_info.value.code == 2
