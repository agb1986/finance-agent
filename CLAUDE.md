# Finance Agent

A personal finance agent built with Claude skills. Skills are invoked by Claude via SKILL.md files and run Python scripts managed by uv.

## Repo Structure

```
finance-agent/
├── .venv/                        # uv virtual environment (root, shared)
├── pyproject.toml                # uv workspace root
├── uv.lock
├── common/                       # shared code, installable as a package
│   ├── pyproject.toml
│   └── src/common/
└── skills/
    └── <skill_name>/
        ├── pyproject.toml        # uv workspace member
        ├── src/<skill_name>/     # skill package (business logic)
        ├── scripts/              # thin entrypoint scripts invoked by Claude
        └── tests/                # all tests for this skill
```

## Skills

Each skill lives in `skills/<skill_name>/` and is a uv workspace member. Skills are invoked by Claude via a `SKILL.md` file at the root of each skill directory.

See `.claude/rules/skills.md` for conventions.

## Environment

- Python managed via `uv`. Always use `uv run` to execute scripts.
- Sync all packages: `uv sync --all-packages`
- Run a script: `uv run skills/<skill_name>/scripts/<script>.py`
- Add a dep to a skill: `uv add <package> --package <skill_name>`

## Common Package

Shared utilities live in `common/`. All skills depend on it via the uv workspace. Import as `from common.<module> import ...`.

## Logging

All scripts must use the shared logger from `common.logger`. Log at critical points (function entry, key decisions, errors, output written).

```python
from common.args import base_parser
from common.logger import get_logger, setup

parser = argparse.ArgumentParser(parents=[base_parser()])
# ... add script-specific args ...
args = parser.parse_args()

logger = setup(args.debug)  # call once in main()
logger = get_logger()       # call anywhere else
```

- `--debug` flag is provided by `base_parser()` — always use it as a parent
- `setup(args.debug)` must be called once in `main()` before any logging
- `logger.debug(...)` — only shown when `--debug` is passed
- `logger.error(...)` — always shown regardless of `--debug`
- Log format: `LEVEL::timestamp::script::function::message`

## Testing

All tests live in `tests/` at the skill root. Each script in `scripts/` must have a corresponding `test_<script>.py` in `tests/`.

### Setup

Add `pytest` and `pytest-cov` as dev dependencies in the skill's `pyproject.toml`:

```toml
[dependency-groups]
dev = ["pytest>=9.0", "pytest-cov>=7.0"]
```

Run tests:
```bash
uv run pytest skills/<skill_name>/tests/ -v
uv run pytest skills/<skill_name>/tests/ --cov --cov-report=term-missing
```

### Conventions

- Use `unittest.mock` (`patch`, `MagicMock`) — no third-party mock libraries
- Mock all I/O boundaries: `feedparser.parse`, `Path.write_text`, `Path.mkdir`, etc.
- Patch module-level constants (e.g. `FEEDS`, `TMP_DIR`) via `patch.object` to isolate tests
- Add a `reset_logger` autouse fixture to clear logger handlers between tests:

```python
@pytest.fixture(autouse=True)
def reset_logger():
    yield
    logging.getLogger("finance_agent").handlers.clear()
```

- Test files in `tests/` import library code directly from the installed package, and import
  thin scripts by inserting `scripts/` into `sys.path`:

```python
# library code — imported directly
from financial_news.fetcher import strip_html, fetch_feed

# thin script — imported via sys.path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import fetch_news
```

### Coverage targets

- Target 90% coverage; 80%+ is acceptable
- The `if __name__ == "__main__"` guard does not need to be covered
