# Coding Standards

## Python

- Python 3.11+
- Use `uv` for all environment and dependency management — never pip directly
- Use `src/` layout for all packages (PEP 517)
- Type hints on all function signatures
- Prefer `pathlib.Path` over `os.path`

## Dependencies

- Declare deps in the skill's `pyproject.toml`, not the root
- All skills must depend on `common` (workspace package)
- Pin ranges loosely (e.g. `>=0.27`) unless a specific version is required

## Script Entrypoints

- Scripts in `scripts/` must be runnable via `uv run`
- Use `argparse` for argument parsing
- Output JSON to stdout for structured data
- Write errors to stderr, not stdout
- Use exit code `0` for success, non-zero for failure

## Style

- Follow PEP 8
- Max line length: 100
- Use f-strings over `.format()`
- No print debugging left in committed code

## Linting & Formatting

All code must pass `ruff` before being committed. Ruff is configured in the root `pyproject.toml` (line length 100, rules: E/W/F/I/UP).

```bash
# Check for lint issues
uv run ruff check .

# Auto-fix all fixable issues
uv run ruff check --fix .

# Format code
uv run ruff format .

# Check formatting without applying (e.g. in CI)
uv run ruff format --check .
```

Always run both `ruff check --fix` and `ruff format` before committing.
