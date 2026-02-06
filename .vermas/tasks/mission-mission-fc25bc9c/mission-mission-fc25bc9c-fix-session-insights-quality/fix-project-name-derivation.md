---
status: done
priority: medium
workflow: null
---
# Fix project name derivation to extract directory names instead of numeric IDs

In parsers/claude.py (and any other parsers that derive project names), fix the project name extraction logic. Currently it produces numeric IDs like 'project-11' instead of real names like 'project-vermas'. The fix: when parsing cwd from session metadata, extract the last meaningful directory component using pathlib or os.path.basename. For example, '/Users/nikpatel/Documents/GitHub/vermas' should yield 'vermas', and '/Users/nikpatel/Documents/GitHub/vermas-experiments/session-insights' should yield 'session-insights'. Also fix the two failing tests in tests/parsers/test_project_derivation.py (TestClaudeProjectDerivation and the Codex narrative variant) so they pass with the corrected logic. Add an explicit test that verifies 'vermas' is extracted from '/Users/nikpatel/Documents/GitHub/vermas'. Run 'uv run pytest tests/parsers/test_project_derivation.py -x -q' to confirm all pass.
