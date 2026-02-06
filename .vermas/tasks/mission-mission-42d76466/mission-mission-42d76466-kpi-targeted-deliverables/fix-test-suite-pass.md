---
status: pending
priority: medium
workflow: 
---

# Fix test suite to pass end-to-end and measure tests_pass KPI

Run `uv run pytest` in the session-insights project directory (`/Users/nikpatel/Documents/GitHub/vermas-experiments/session-insights`). Identify all failing tests, fix them (test code or implementation as needed), and ensure the suite passes with 90%+ of tests green. After fixing, create a script `scripts/measure_kpis.sh` that runs the test suite and outputs a JSON line like `{"kpi": "tests_pass", "value": <pass_rate>, "unit": "%"}`. Commit all fixes. This is the highest-priority task because a passing test suite validates all other work and is the easiest KPI to move.
