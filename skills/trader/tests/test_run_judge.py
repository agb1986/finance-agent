"""Tests for run_judge.py and trader.judge."""

import importlib.util
import json
import logging
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from trader.judge import format_transcript, parse_verdict, run_judge

_spec = importlib.util.spec_from_file_location(
    "trader_run_judge", Path(__file__).parent.parent / "scripts" / "run_judge.py"
)
run_judge_script = importlib.util.module_from_spec(_spec)
sys.modules["trader_run_judge"] = run_judge_script
_spec.loader.exec_module(run_judge_script)


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
    "panel": {"fundamental": "f"},
    "debate": {"bull": "bull", "bear": "bear"},
    "judge": "You are the judge.",
}

SAMPLE_TRANSCRIPT = [
    {"round": 1, "side": "bull", "argument": "b1"},
    {"round": 1, "side": "bear", "argument": "r1"},
]

SAMPLE_VERDICT = {
    "scorecard": {"bull": {"total": 40}, "bear": {"total": 30}},
    "winner": "bull",
    "confidence": "high",
    "key_unresolved_question": "Will margins hold?",
    "verdict": "Bull wins.",
}


def _fake_response(text: str) -> MagicMock:
    block = MagicMock()
    block.type = "text"
    block.text = text
    response = MagicMock()
    response.content = [block]
    response.usage = SimpleNamespace(
        input_tokens=100,
        output_tokens=50,
        cache_read_input_tokens=0,
        cache_creation_input_tokens=0,
    )
    return response


# ── format_transcript / parse_verdict / run_judge (library) ───────────────────


class TestFormatTranscript:
    def test_renders_rounds_and_sides(self):
        text = format_transcript(SAMPLE_TRANSCRIPT)
        assert "ROUND 1 — BULL:\nb1" in text
        assert "ROUND 1 — BEAR:\nr1" in text


class TestParseVerdict:
    def test_parses_plain_json(self):
        assert parse_verdict(json.dumps(SAMPLE_VERDICT)) == SAMPLE_VERDICT

    def test_strips_json_fence(self):
        fenced = f"```json\n{json.dumps(SAMPLE_VERDICT)}\n```"
        assert parse_verdict(fenced) == SAMPLE_VERDICT

    def test_strips_bare_fence(self):
        fenced = f"```\n{json.dumps(SAMPLE_VERDICT)}\n```"
        assert parse_verdict(fenced) == SAMPLE_VERDICT

    def test_fallback_on_invalid_json(self):
        result = parse_verdict("the bull wins, obviously")
        assert result["raw"] == "the bull wins, obviously"
        assert "parse_error" in result


class TestRunJudge:
    def test_returns_parsed_verdict(self):
        client = MagicMock()
        client.messages.create.return_value = _fake_response(json.dumps(SAMPLE_VERDICT))

        result, _ = run_judge(client, SAMPLE_CONFIG, "AMZN", SAMPLE_TRANSCRIPT)

        assert result == SAMPLE_VERDICT

    def test_uses_judge_model_and_system(self):
        client = MagicMock()
        client.messages.create.return_value = _fake_response("{}")

        run_judge(client, SAMPLE_CONFIG, "AMZN", SAMPLE_TRANSCRIPT)

        call = client.messages.create.call_args
        assert call.kwargs["model"] == "claude-opus-4-8"
        assert call.kwargs["system"] == "You are the judge."

    def test_prompt_contains_symbol_and_transcript(self):
        client = MagicMock()
        client.messages.create.return_value = _fake_response("{}")

        run_judge(client, SAMPLE_CONFIG, "AMZN", SAMPLE_TRANSCRIPT)

        prompt = client.messages.create.call_args.kwargs["messages"][0]["content"]
        assert prompt.startswith("Stock: AMZN")
        assert "ROUND 1 — BULL:\nb1" in prompt


# ── main (script) ─────────────────────────────────────────────────────────────

# Panel + debate tokens already accumulated in the debate file.
UPSTREAM_USAGE = {
    "claude-sonnet-4-6": {
        "input_tokens": 200,
        "output_tokens": 100,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
        "calls": 2,
    },
    "claude-opus-4-8": {
        "input_tokens": 400,
        "output_tokens": 200,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
        "calls": 4,
    },
}
# What the judge call itself consumed.
SAMPLE_USAGE = {
    "claude-opus-4-8": {
        "input_tokens": 300,
        "output_tokens": 150,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
        "calls": 1,
    }
}


class TestMain:
    def _debate_file(self, tmp_path: Path) -> Path:
        debate_file = tmp_path / "debate_AMZN_x.json"
        debate_file.write_text(
            json.dumps({"symbol": "AMZN", "transcript": SAMPLE_TRANSCRIPT, "usage": UPSTREAM_USAGE})
        )
        return debate_file

    def _patches(self, tmp_path, **overrides):
        defaults = {
            "get_client": MagicMock(),
            "load_config": MagicMock(return_value=SAMPLE_CONFIG),
            "run_judge": MagicMock(return_value=(SAMPLE_VERDICT, SAMPLE_USAGE)),
        }
        defaults.update(overrides)
        return (
            patch.object(run_judge_script, "TMP_DIR", tmp_path / "out"),
            patch.object(run_judge_script, "get_client", defaults["get_client"]),
            patch.object(run_judge_script, "load_config", defaults["load_config"]),
            patch.object(run_judge_script, "run_judge", defaults["run_judge"]),
        )

    def test_writes_json_and_prints_path(self, tmp_path, capsys):
        debate_file = self._debate_file(tmp_path)
        p1, p2, p3, p4 = self._patches(tmp_path)
        with p1, p2, p3, p4:
            with patch("sys.argv", ["run_judge.py", "--input", str(debate_file)]):
                run_judge_script.main()

        output_path = Path(capsys.readouterr().out.strip())
        assert output_path.exists()
        assert "verdict_AMZN_" in output_path.name

        data = json.loads(output_path.read_text())
        assert data["symbol"] == "AMZN"
        assert data["verdict"] == SAMPLE_VERDICT
        # The verdict file carries the whole chain: panel + debate + judge.
        assert data["usage"]["claude-sonnet-4-6"]["calls"] == 2
        assert data["usage"]["claude-opus-4-8"]["calls"] == 5
        assert data["usage"]["claude-opus-4-8"]["input_tokens"] == 700

    def test_passes_transcript_to_judge(self, tmp_path):
        debate_file = self._debate_file(tmp_path)
        mock_run = MagicMock(return_value=(SAMPLE_VERDICT, SAMPLE_USAGE))
        p1, p2, p3, p4 = self._patches(tmp_path, run_judge=mock_run)
        with p1, p2, p3, p4:
            with patch("sys.argv", ["run_judge.py", "--input", str(debate_file)]):
                run_judge_script.main()

        assert mock_run.call_args.args[3] == SAMPLE_TRANSCRIPT

    def test_exits_on_missing_input(self, tmp_path):
        p1, p2, p3, p4 = self._patches(tmp_path)
        with p1, p2, p3, p4:
            with patch("sys.argv", ["run_judge.py", "--input", "/nope/missing.json"]):
                with pytest.raises(SystemExit) as exc_info:
                    run_judge_script.main()

        assert exc_info.value.code == 1

    def test_exits_on_malformed_input(self, tmp_path):
        bad_file = tmp_path / "bad.json"
        bad_file.write_text('{"symbol": "AMZN"}')  # no "transcript" key
        p1, p2, p3, p4 = self._patches(tmp_path)
        with p1, p2, p3, p4:
            with patch("sys.argv", ["run_judge.py", "--input", str(bad_file)]):
                with pytest.raises(SystemExit) as exc_info:
                    run_judge_script.main()

        assert exc_info.value.code == 1

    def test_exits_on_judge_error(self, tmp_path):
        debate_file = self._debate_file(tmp_path)
        mock_run = MagicMock(side_effect=RuntimeError("API error"))
        p1, p2, p3, p4 = self._patches(tmp_path, run_judge=mock_run)
        with p1, p2, p3, p4:
            with patch("sys.argv", ["run_judge.py", "--input", str(debate_file)]):
                with pytest.raises(SystemExit) as exc_info:
                    run_judge_script.main()

        assert exc_info.value.code == 1

    def test_input_required(self):
        with patch("sys.argv", ["run_judge.py"]):
            with pytest.raises(SystemExit) as exc_info:
                run_judge_script.main()

        assert exc_info.value.code == 2
