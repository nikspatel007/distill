# Mission: Session Insights - Rich Output Quality

The session-insights CLI exists and runs, but the generated Obsidian notes are empty/useless. The tool parses data correctly but loses it before formatting. Fix the data pipeline so notes contain rich, actionable content.

## What Needs Fixing

### Problem 1: Data Model Mismatch (Critical)

Two incompatible `BaseSession` classes exist:
- `parsers/models.py` — used by parsers, has `messages`, `tool_calls` fields
- `models/__init__.py` — expected by formatter, has `tools_used`, `outcomes`, `turns` fields

Compatibility properties in `parsers/models.py` return empty data:
- `outcomes` always returns `[]`
- `tools_used` returns empty when `tool_calls` is empty
- VerMAS-specific data (signals, learnings, task_description) is never exposed to formatter

**Fix**: Unify to ONE BaseSession model. Remove the duplicate. Make all parsers populate the fields the formatter needs.

### Problem 2: VerMAS Sessions Show "Task: unknown"

The VerMAS parser extracts task_name, task_description, signals, learnings, improvements — but the formatter never renders them. The formatter's `format_session()` only uses generic BaseSession fields.

**Fix**: The formatter should render VerMAS-specific fields when available: task description, agent signals, learnings, quality assessment, cycle info.

### Problem 3: Claude Sessions Missing Conversation Content

Claude sessions have rich conversation data (messages with tool calls), but notes show "_Conversation not included._" by default and even with `--include-conversation` the turns are minimal.

**Fix**: Extract and display: what the user asked, what tools were used and why, what was accomplished, key decisions made.

### Problem 4: Home Directory Discovery

The CLI only scans the `--dir` path for `.claude/` and `.codex/` subdirectories. Global session history lives at `~/.claude/` and `~/.codex/` (home directory). Users should be able to analyze ALL their sessions, not just project-local ones.

**Fix**: Add `--global` flag or `--home` flag that also scans `~/.claude/` and `~/.codex/`. Alternatively, if `--dir ~` is passed, ensure it works correctly.

## Technical Details

### Data Flow (Current - Broken)
```
Parser extracts data → stores in parsers.BaseSession
                      → formatter expects models.BaseSession interface
                      → compatibility properties return empty
                      → notes are empty
```

### Data Flow (Target - Working)
```
Parser extracts data → stores in unified BaseSession
                      → formatter renders all available fields
                      → notes contain rich content
```

### Key Files
- `src/session_insights/parsers/models.py` — parser base model (has real data)
- `src/session_insights/models/__init__.py` — formatter model (expected interface)
- `src/session_insights/formatters/obsidian.py` — renders sessions to markdown
- `src/session_insights/parsers/claude.py` — Claude session parser
- `src/session_insights/parsers/codex.py` — Codex session parser
- `src/session_insights/parsers/vermas.py` — VerMAS session parser
- `src/session_insights/cli.py` — CLI entry point
- `src/session_insights/core.py` — discovery and analysis orchestration

## Success KPIs

| KPI | Target | How Measured |
|-----|--------|--------------|
| Note Content Richness | 90% | Sessions with non-empty tools_used, outcomes, or conversation data |
| VerMAS Task Visibility | 100% | VerMAS sessions show task_description, signals, learnings |
| Test Coverage | 90% | `uv run pytest tests/ --cov=session_insights --cov-fail-under=90` |
| CLI Runs Clean | 100% | `uv run python -m session_insights analyze --dir ~ --output /tmp/test-vault` exits 0 with notes |

## Constraints

- Python 3.11+
- Minimal dependencies (prefer stdlib)
- Must work offline (no API calls for analysis)
- Obsidian notes must be standalone (no plugins required)
- Do NOT break existing tests — refactor incrementally
- Run tests after every change: `uv run pytest tests/ -x -q`

## Definition of Done

- [ ] ONE unified BaseSession model (no duplicate)
- [ ] VerMAS notes show: task description, signals, learnings, quality
- [ ] Claude notes show: conversation summary, tools used, outcomes
- [ ] Daily summaries aggregate real data (not "unknown")
- [ ] `--dir ~` or `--global` scans home directory sessions
- [ ] All tests pass with 90%+ coverage
- [ ] Dogfood: run on real data, notes are genuinely useful
