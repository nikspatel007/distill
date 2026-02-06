---
status: done
priority: medium
workflow: null
---
# Implement project detection from cwd metadata with accuracy measurement

In the session-insights codebase, enhance the session parser/analyzer to extract the project name from the `cwd` field in session metadata. Logic: parse the cwd path, extract the repository/project directory name (e.g., `/Users/nikpatel/Documents/GitHub/vermas` → `vermas`). Add a `project` field to the enhanced session note frontmatter. Handle edge cases: home directory sessions (no project), nested repos, multiple cwds in one session (use most frequent). Write a measurement script that samples 50+ session notes and checks if project detection is present and plausible, outputting `{"kpi": "project_detection", "value": <accuracy>, "unit": "%"}`. Target: 70%+ accuracy. Include unit tests for the detection logic.
