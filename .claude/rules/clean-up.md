# Clean-up Rule

When the user asks you to clean up, clear tmp files, or tidy the workspace, delete all files in every skill's `tmp/` directory.

## Command

```bash
rm -f skills/*/tmp/*
```

After running, confirm to the user which directories were cleared and how many files were removed.
