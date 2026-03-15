# Git Workflow

Follow these steps **in order** whenever performing a git commit, push, or PR action.

---

## Step 1 — Run tests

```bash
uv run pytest
```

- Tests must pass and coverage must be ≥ 85% (enforced automatically by pytest config).
- If any tests fail or coverage is below threshold, **stop and ask the user** if they would like you to fix the issues before continuing.

---

## Step 2 — Run linter

```bash
uv run ruff check .
```

- All checks must pass.
- If there are fixable issues, offer to run `uv run ruff check --fix . && uv run ruff format .` automatically.
- If there are unfixable issues, **stop and ask the user** if they would like you to fix them before continuing.

---

## Step 3 — Stage all changes

```bash
git add -A
```

---

## Step 4 — Commit using Conventional Commits

Follow the [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) standard:

```
<type>[optional scope]: <description>

[optional body]

[optional footer]
```

Common types: `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `ci`

Examples:
```
feat(financial-news): add RSS feed fetching script
fix(logger): remove duplicate handler on repeated setup calls
chore: add ruff linting and formatting
test(financial-news): add fetch_news unit tests with 98% coverage
```

---

## Step 5 — Push to remote branch

```bash
git push
```

If the branch has no upstream yet:
```bash
git push -u origin <branch-name>
```

---

## Step 6 — Create or update PR

Ask the user: **"Would you like to create a new draft PR, or update the current open PR?"**

### Creating a new draft PR

```bash
gh pr create --draft --title "<title>" --body "$(cat <<'EOF'
## Summary
<bullet list of all changes in this PR>

## Commits
<bullet list of all commits in this PR>

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

### Updating an existing PR

First, fetch the current PR body so the existing summary is preserved:

```bash
gh api repos/<owner>/<repo>/pulls/<number> --jq '.body'
```

Then update the PR by **appending** the new changes to the existing summary and commits list — do not discard what was already there:

```bash
gh api repos/<owner>/<repo>/pulls/<number> -X PATCH -f body="$(cat <<'EOF'
## Summary
<existing bullet points from current PR body>
<new bullet points for changes in this update>

## Commits
<existing commits from current PR body>
<new commits added since last update>

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)" --jq '.html_url'
```

Use `git log origin/main..HEAD --oneline` to get the full commit list for the PR body.
