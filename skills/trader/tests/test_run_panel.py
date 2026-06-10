"""Tests for run_panel.py and trader.{roles,client,panel}."""

import importlib.util
import json
import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from trader.client import call_role, get_client
from trader.panel import build_panel_prompt, run_panel
from trader.roles import CONFIG_PATH, REQUIRED_KEYS, load_config

_spec = importlib.util.spec_from_file_location(
    "trader_run_panel", Path(__file__).parent.parent / "scripts" / "run_panel.py"
)
run_panel_script = importlib.util.module_from_spec(_spec)
sys.modules["trader_run_panel"] = run_panel_script
_spec.loader.exec_module(run_panel_script)


@pytest.fixture(autouse=True)
def reset_logger():
    yield
    logging.getLogger("finance_agent").handlers.clear()


def _fake_response(text: str) -> MagicMock:
    block = MagicMock()
    block.type = "text"
    block.text = text
    response = MagicMock()
    response.content = [block]
    return response


SAMPLE_CONFIG = {
    "models": {
        "panel": "claude-sonnet-4-6",
        "debate": "claude-opus-4-8",
        "judge": "claude-fable-5",
    },
    "max_tokens": {"panel": 1024, "debate": 2048, "judge": 2048},
    "panel": {"fundamental": "You are a fundamental analyst.", "risk": "You are a risk manager."},
    "debate": {"bull": "You are the bull.", "bear": "You are the bear."},
    "judge": "You are the judge.",
}


# ── load_config (library) ─────────────────────────────────────────────────────


class TestLoadConfig:
    def test_loads_shipped_config(self):
        config = load_config()
        assert REQUIRED_KEYS <= set(config)
        assert set(config["panel"]) == {"fundamental", "technical", "macro", "sentiment", "risk"}
        assert set(config["debate"]) == {"bull", "bear"}
        assert config["models"]["panel"] == "claude-sonnet-4-6"
        assert config["models"]["debate"] == "claude-opus-4-8"
        assert config["models"]["judge"] == "claude-fable-5"

    def test_shipped_config_path_exists(self):
        assert CONFIG_PATH.exists()

    def test_raises_on_missing_keys(self, tmp_path):
        bad = tmp_path / "roles.yaml"
        bad.write_text("models:\n  panel: claude-sonnet-4-6\n")
        with pytest.raises(ValueError, match="missing keys"):
            load_config(bad)


# ── get_client / call_role (library) ──────────────────────────────────────────


class TestGetClient:
    def test_raises_without_api_key(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
            get_client()

    def test_returns_client_with_api_key(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        with patch("trader.client.Anthropic") as mock_anthropic:
            client = get_client()
        mock_anthropic.assert_called_once()
        assert client is mock_anthropic.return_value


class TestCallRole:
    def test_passes_request_fields(self):
        client = MagicMock()
        client.messages.create.return_value = _fake_response("brief text")

        result = call_role(client, "claude-sonnet-4-6", "system prompt", "user msg", 1024)

        assert result == "brief text"
        client.messages.create.assert_called_once_with(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system="system prompt",
            messages=[{"role": "user", "content": "user msg"}],
        )

    def test_ignores_non_text_blocks(self):
        thinking = MagicMock()
        thinking.type = "thinking"
        text = MagicMock()
        text.type = "text"
        text.text = "answer"
        response = MagicMock()
        response.content = [thinking, text]
        client = MagicMock()
        client.messages.create.return_value = response

        assert call_role(client, "m", "s", "u", 10) == "answer"

    def test_concatenates_multiple_text_blocks(self):
        client = MagicMock()
        response = MagicMock()
        blocks = []
        for part in ("foo", "bar"):
            block = MagicMock()
            block.type = "text"
            block.text = part
            blocks.append(block)
        response.content = blocks
        client.messages.create.return_value = response

        assert call_role(client, "m", "s", "u", 10) == "foobar"


# ── run_panel (library) ───────────────────────────────────────────────────────


class TestBuildPanelPrompt:
    def test_without_context(self):
        assert build_panel_prompt("AMZN", None) == "Analyse: AMZN"

    def test_with_context(self):
        prompt = build_panel_prompt("AMZN", '{"price": 207.67}')
        assert prompt.startswith("Analyse: AMZN")
        assert "MARKET DATA:" in prompt
        assert '{"price": 207.67}' in prompt


class TestRunPanel:
    def test_returns_brief_per_role(self):
        client = MagicMock()
        client.messages.create.return_value = _fake_response("a brief")

        result = run_panel(client, SAMPLE_CONFIG, "AMZN")

        assert set(result) == {"fundamental", "risk"}
        assert all(brief == "a brief" for brief in result.values())
        assert client.messages.create.call_count == 2

    def test_all_roles_get_same_prompt_and_panel_model(self):
        client = MagicMock()
        client.messages.create.return_value = _fake_response("brief")

        run_panel(client, SAMPLE_CONFIG, "AMZN", context="ctx")

        for call in client.messages.create.call_args_list:
            assert call.kwargs["model"] == "claude-sonnet-4-6"
            assert call.kwargs["messages"][0]["content"] == build_panel_prompt("AMZN", "ctx")

    def test_each_role_gets_own_system_prompt(self):
        client = MagicMock()
        client.messages.create.return_value = _fake_response("brief")

        run_panel(client, SAMPLE_CONFIG, "AMZN")

        systems = {call.kwargs["system"] for call in client.messages.create.call_args_list}
        assert systems == set(SAMPLE_CONFIG["panel"].values())


# ── main (script) ─────────────────────────────────────────────────────────────

SAMPLE_PANEL = {"fundamental": "buy", "risk": "2%"}


class TestMain:
    def _patches(self, tmp_path, **overrides):
        defaults = {
            "get_client": MagicMock(),
            "load_config": MagicMock(return_value=SAMPLE_CONFIG),
            "run_panel": MagicMock(return_value=SAMPLE_PANEL),
        }
        defaults.update(overrides)
        return (
            patch.object(run_panel_script, "TMP_DIR", tmp_path),
            patch.object(run_panel_script, "get_client", defaults["get_client"]),
            patch.object(run_panel_script, "load_config", defaults["load_config"]),
            patch.object(run_panel_script, "run_panel", defaults["run_panel"]),
        )

    def test_writes_json_and_prints_path(self, tmp_path, capsys):
        p1, p2, p3, p4 = self._patches(tmp_path)
        with p1, p2, p3, p4:
            with patch("sys.argv", ["run_panel.py", "--symbol", "amzn"]):
                run_panel_script.main()

        output_path = Path(capsys.readouterr().out.strip())
        assert output_path.exists()
        assert "panel_AMZN_" in output_path.name

        data = json.loads(output_path.read_text())
        assert data["symbol"] == "AMZN"
        assert data["panel"] == SAMPLE_PANEL
        assert data["context_file"] is None

    def test_passes_context_file_content(self, tmp_path):
        context_file = tmp_path / "quote.json"
        context_file.write_text('{"price": 1}')
        mock_run = MagicMock(return_value=SAMPLE_PANEL)
        p1, p2, p3, p4 = self._patches(tmp_path, run_panel=mock_run)
        with p1, p2, p3, p4:
            argv = ["run_panel.py", "--symbol", "AMZN", "--context-file", str(context_file)]
            with patch("sys.argv", argv):
                run_panel_script.main()

        assert mock_run.call_args.args[3] == '{"price": 1}'

    def test_exits_on_missing_context_file(self, tmp_path):
        p1, p2, p3, p4 = self._patches(tmp_path)
        with p1, p2, p3, p4:
            argv = ["run_panel.py", "--symbol", "AMZN", "--context-file", "/nope/missing.json"]
            with patch("sys.argv", argv):
                with pytest.raises(SystemExit) as exc_info:
                    run_panel_script.main()

        assert exc_info.value.code == 1

    def test_exits_on_panel_error(self, tmp_path):
        mock_run = MagicMock(side_effect=RuntimeError("API error"))
        p1, p2, p3, p4 = self._patches(tmp_path, run_panel=mock_run)
        with p1, p2, p3, p4:
            with patch("sys.argv", ["run_panel.py", "--symbol", "AMZN"]):
                with pytest.raises(SystemExit) as exc_info:
                    run_panel_script.main()

        assert exc_info.value.code == 1
        assert list(tmp_path.iterdir()) == []

    def test_exits_without_api_key(self, tmp_path):
        mock_client = MagicMock(side_effect=RuntimeError("ANTHROPIC_API_KEY is not set"))
        p1, p2, p3, p4 = self._patches(tmp_path, get_client=mock_client)
        with p1, p2, p3, p4:
            with patch("sys.argv", ["run_panel.py", "--symbol", "AMZN"]):
                with pytest.raises(SystemExit) as exc_info:
                    run_panel_script.main()

        assert exc_info.value.code == 1

    def test_symbol_required(self):
        with patch("sys.argv", ["run_panel.py"]):
            with pytest.raises(SystemExit) as exc_info:
                run_panel_script.main()

        assert exc_info.value.code == 2
