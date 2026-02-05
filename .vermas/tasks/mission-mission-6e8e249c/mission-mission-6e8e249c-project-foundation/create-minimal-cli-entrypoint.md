---
status: pending
priority: medium
workflow: 
---

# Create minimal CLI entry point

Create a minimal cli.py that can be executed but does nothing yet:

1. Create src/session_insights/cli.py with:
   - Import click
   - Create a single @click.group() called 'main'
   - Add a simple @main.command() called 'version' that prints '0.1.0'
   - Add if __name__ == '__main__': main()

2. Test by running: uv run python -m session_insights.cli version

This task creates ONLY the minimal CLI structure. No subcommands like 'analyze' yet. Keep it as simple as possible to ensure it works.
