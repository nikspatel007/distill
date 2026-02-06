# Mission: Fix Remaining Session-Insights Quality Issues

Previous mission completed 5 cycles and implemented the core features. However, several quality issues remain that prevent the tool from producing genuinely useful output.

## Current State

The tool runs (`uv run python -m session_insights analyze --dir <project> --global --output insights/`) and produces:
- 11,714 sessions parsed
- 1,912 project notes in `projects/`
- Daily summaries in `daily/`
- Session notes in `sessions/`
- 459 tests passing

## Remaining Issues (Must Fix)

### 1. Project Names Are Numeric IDs
Project notes have names like `project-11.md`, `project-103.md` instead of real project names like `project-vermas.md`, `project-session-insights.md`. The project detection extracts numeric IDs instead of the actual directory name from `cwd`.

**Fix**: Parse the cwd path to extract the last meaningful directory component as the project name. For example:
- `/Users/nikpatel/Documents/GitHub/vermas` → `vermas`
- `/Users/nikpatel/Documents/GitHub/vermas-experiments/session-insights` → `session-insights`

### 2. Session Summaries Show Raw Prompts
Many session notes show the raw first user prompt as the summary (e.g., `<command-message>init</command-message>` or `analyze home`). The narrative field should contain a human-readable description of what was accomplished.

**Fix**: Generate narratives from session data - tools used, outcomes, tags, duration. Skip raw prompts. Example: "45-minute session in vermas using Bash, Read, Edit. Modified 15 files across the workflow engine."

### 3. Weekly Digests Not Generated
The `weekly/` folder is not created when running the analyze command. The weekly digest formatter may exist but isn't wired into the CLI pipeline.

**Fix**: Wire the weekly digest formatter into the analyze pipeline in `core.py` / `cli.py`. Ensure `weekly/` folder is created with one file per ISO week.

### 4. Two Failing Tests
`tests/parsers/test_project_derivation.py::TestClaudeProjectDerivation::test_narrative_populated` and the Codex variant are failing.

**Fix**: Fix the narrative population logic so these tests pass.

### 5. Coverage Dropped to 88%
New code was added without sufficient test coverage, dropping from 94% to 88%.

**Fix**: Add tests for uncovered code paths, especially in new measurers and formatters. Target 90%+.

## Success Criteria

| KPI | Target | Measurement |
|-----|--------|-------------|
| Project Names | 95% | Projects have real names (not numeric IDs) when `cwd` is available |
| Narrative Quality | 80% | Sessions have narratives that are NOT raw prompts (> 10 words, no XML tags) |
| Weekly Digests | 100% | `weekly/` folder exists with files after running analyze |
| Tests Pass | 100% | All tests pass (`uv run pytest tests/ -q`) |
| Coverage | 90%+ | `uv run pytest tests/ --cov=session_insights --cov-fail-under=90` |

## Key Files

| File | Issue |
|------|-------|
| `parsers/claude.py` | Project detection from cwd - fix to return directory name not numeric ID |
| `parsers/codex.py` | Same project detection fix |
| `parsers/vermas.py` | Same project detection fix |
| `parsers/models.py` | `project` field derivation logic |
| `formatters/obsidian.py` | May need to use improved project name |
| `core.py` | Wire weekly digest generation into pipeline |
| `cli.py` | Ensure weekly output path is passed through |
| `tests/parsers/test_project_derivation.py` | Fix 2 failing tests |

## Constraints

- Don't break existing session note format
- No external API calls
- Python 3.11+
- Obsidian-compatible markdown
- All changes must have tests
