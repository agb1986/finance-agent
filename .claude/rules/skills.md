# Skill Conventions

## Directory Layout

Each skill follows this structure:

```
skills/<skill_name>/
├── SKILL.md              # Claude skill definition (invocation instructions)
├── pyproject.toml        # uv workspace member, declares dependencies
├── src/
│   └── <skill_name>/
│       ├── __init__.py
│       └── ...           # skill logic (not scripts)
├── scripts/
│   └── <action>.py       # thin entrypoints, called by Claude via uv run
└── tests/
    └── test_<action>.py  # tests for scripts and library modules
```

## SKILL.md Format

Each skill must have a `SKILL.md` that tells Claude:
- What the skill does
- When to invoke it
- Which scripts to run and with what arguments
- Expected output format

The first step in **How to invoke** must always be `Step 0 — Verify prerequisites`. See `CLAUDE.md` for the required check block and failure behaviour.

## Scripts

Scripts in `scripts/` are thin entrypoints. All business logic lives in `src/<skill_name>/`. Scripts should:
- Accept arguments via `sys.argv` or `argparse`
- Print structured output (JSON preferred) to stdout
- Exit with a non-zero code on failure

## Adding a New Skill

1. Create `skills/<skill_name>/` following the layout above
2. Add a `pyproject.toml` declaring `common` as a dependency
3. Write logic in `src/<skill_name>/`
4. Write thin script entrypoints in `scripts/`
5. Write tests in `tests/`
6. Write a `SKILL.md` describing invocation — include `Step 0 — Verify prerequisites` as the first step
7. Run `uv sync --all-packages` to register the new workspace member
