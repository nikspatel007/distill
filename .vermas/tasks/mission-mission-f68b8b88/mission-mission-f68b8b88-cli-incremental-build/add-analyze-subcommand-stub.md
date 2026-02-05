---
status: done
priority: medium
workflow: null
---
# Add analyze subcommand stub with --dir argument

Add the `analyze` subcommand to the CLI with a single --dir argument using Click. The implementation should: (1) Accept --dir path argument, (2) Validate the directory exists, (3) Print 'Analyzing: <path>' and exit successfully. No actual parsing logic yet. Add pytest test for the subcommand. Signal done when `uv run session-insights analyze --dir .` works.
