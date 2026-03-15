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
        ├── src/<skill_name>/     # skill package
        └── scripts/              # thin entrypoint scripts invoked by Claude
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
