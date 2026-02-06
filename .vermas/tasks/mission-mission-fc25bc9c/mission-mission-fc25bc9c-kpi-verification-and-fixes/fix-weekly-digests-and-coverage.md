---
status: pending
priority: medium
workflow: 
---

# Wire weekly digests end-to-end and close test coverage to 90%+

Based on `KPI_BASELINE.md` measurements, fix weekly digest generation and coverage gaps.

In the session-insights codebase (`/Users/nikpatel/Documents/GitHub/vermas-experiments/session-insights`):

Weekly Digests:
1. Check if `weekly/` folder was created in the baseline run. If not, find where weekly digest formatting code lives and wire it into the analyze pipeline in `core.py` / `cli.py`
2. Ensure the pipeline creates `weekly/` folder with one file per ISO week containing actual digest content (summaries of daily work, key accomplishments, patterns)
3. Run the pipeline on real historical data to validate: `uv run python -m session_insights analyze --dir /Users/nikpatel/Documents/GitHub/vermas --global --output /tmp/weekly-test/`
4. Verify weekly/ folder has ISO-week files with real content

Test Coverage:
5. Read the coverage report from `KPI_BASELINE.md` to identify specific uncovered modules
6. Write targeted tests for the highest-impact uncovered code paths (focus on modules with lowest coverage first)
7. Run full test suite with coverage: `uv run pytest tests/ --cov=session_insights --cov-report=term-missing -q`
8. Ensure all tests pass AND coverage is 90%+

Targets: weekly_digests=100% (folder exists with real content), coverage=90%+, tests_pass=100%
