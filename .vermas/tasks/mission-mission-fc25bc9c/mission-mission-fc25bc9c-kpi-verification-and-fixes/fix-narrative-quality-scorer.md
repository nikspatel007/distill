---
status: pending
priority: medium
workflow: 
---

# Build automated narrative scorer and fix quality to reach 80%+

Based on `KPI_BASELINE.md` measurements, fix narrative quality issues.

In the session-insights codebase (`/Users/nikpatel/Documents/GitHub/vermas-experiments/session-insights`):
1. Read `KPI_BASELINE.md` to understand the current narrative_quality percentage and common failure patterns
2. Build an automated narrative quality scorer that REJECTS:
   - Raw prompts containing XML tags (e.g., `<command-message>`, `<system-reminder>`)
   - Summaries under 10 words
   - Literal command text (e.g., `analyze home`, `init`)
   - Summaries that are just file paths or tool names
3. Fix the narrative generation code to produce quality summaries from session metadata: tools used, files modified, duration, outcomes. Example: '45-minute session in vermas using Bash, Read, Edit. Modified 15 files across the workflow engine.'
4. Add tests for the scorer and the improved narrative generation
5. Run `uv run pytest tests/ -x -q` to confirm all tests pass

Target: 80%+ of session narratives should pass the quality scorer.
