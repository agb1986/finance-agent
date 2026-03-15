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
└── scripts/
    └── <action>.py       # thin entrypoints, called by Claude via uv run
```

## SKILL.md Format

Each skill must have a `SKILL.md` that tells Claude:
- What the skill does
- When to invoke it
- Which scripts to run and with what arguments
- Expected output format

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
5. Write a `SKILL.md` describing invocation
6. Run `uv sync --all-packages` to register the new workspace member
