# Mission: Project-Based Narrative Insights

The session-insights tool generates raw session notes (13k+ files). These are data dumps - useful for search but not human-readable narratives. Transform them into meaningful project-based insights that tell the story of what was built.

## Current State

Raw session notes contain:
- Session ID, timestamp, duration
- Tools used (Bash: 54, Read: 27, Edit: 13...)
- Outcomes (Modified 15 files, Ran 54 commands)
- Auto-tags (#debugging, #feature, #testing)
- Summary (first user prompt, often cryptic)

Missing:
- **Project context** - which repo/project was this session working on?
- **Narrative summary** - what was actually accomplished in human terms?
- **Cross-session story** - how do multiple sessions connect into a coherent project history?
- **Key decisions** - what architectural choices were made and why?

## Target Output

### 1. Project Notes (new)

One note per project (detected from `cwd` in session metadata):

```markdown
# Project: vermas

## Overview
Multi-agent task orchestration system with Temporal workflows.

## Timeline
- **Started:** 2026-01-06
- **Sessions:** 847
- **Total Time:** 142 hours

## Major Milestones
- Jan 6-10: Initial Temporal workflow setup
- Jan 15-18: Agent router HTTP API
- Jan 20-25: Meeting system for collaborative reviews
- Jan 28-Feb 5: Mission workflow with KPI evaluation

## Key Decisions
- Chose Temporal over Celery for workflow orchestration
- PostgreSQL for event sourcing instead of Redis
- tmux-based agent isolation

## Related Sessions
- [[session-2026-01-06-0101-521eaf47]]: PR merge and workflow setup
- [[session-2026-01-15-1421-abc123]]: Agent router implementation
...
```

### 2. Weekly Digest (new)

Human-readable weekly summary:

```markdown
# Week of 2026-01-27

## What Got Done
- Implemented meeting trigger system for post-workflow reviews
- Fixed timezone bugs in session-insights parser
- Added cleanup trigger for tmux/worktree resources

## Challenges Faced
- Agent command execution timing issues (needed Enter key nudges)
- Signal ordering bugs in state machine

## Tools Most Used
Bash (2,340), Read (890), Edit (456)

## Projects Touched
- vermas (78 sessions)
- session-insights (23 sessions)
```

### 3. Enhanced Session Notes (improve existing)

Add project detection and narrative summary:

```markdown
---
project: vermas  # NEW - detected from cwd
narrative: "Fixed the cleanup trigger to remove orphaned tmux sessions after workflow completion"  # NEW
---
```

## Implementation Approach

### Phase 1: Project Detection
- Parse `cwd` from session metadata to identify project
- Group sessions by project
- Extract project name from path (last directory component)

### Phase 2: Narrative Generation
- Use session summary + outcomes + tools to generate human-readable narrative
- For VerMAS sessions: use task_name + signals + outcome
- Keep it concise (1-2 sentences)

### Phase 3: Project Aggregation
- Create `projects/` folder with one note per project
- Aggregate sessions, calculate totals
- Extract milestones from session dates + summaries
- Link back to individual sessions

### Phase 4: Weekly Digests
- Create `weekly/` folder
- Group sessions by ISO week
- Summarize accomplishments, challenges, tools

## Key Files to Modify

| File | Change |
|------|--------|
| `parsers/claude.py` | Extract `cwd` from session metadata |
| `parsers/models.py` | Add `project` and `narrative` fields to BaseSession |
| `formatters/obsidian.py` | Add project field to frontmatter |
| `formatters/project.py` | **Create** - Project note formatter |
| `formatters/weekly.py` | **Create** - Weekly digest formatter |
| `cli.py` | Add project and weekly generation to analyze command |
| `core.py` | Add project grouping and aggregation logic |

## Success Criteria

| KPI | Target | Measurement |
|-----|--------|-------------|
| Project Detection | 95% | Sessions with non-empty `project` field |
| Narrative Quality | 80% | Sessions with narrative != summary (improved) |
| Project Notes | 100% | Every detected project has a note |
| Weekly Digests | 100% | Every week with sessions has a digest |
| Tests Pass | 90%+ | `uv run pytest tests/ --cov-fail-under=90` |

## Constraints

- Don't break existing session note format (additive changes only)
- No external API calls (offline-only analysis)
- Python 3.11+, minimal dependencies
- Obsidian-compatible markdown

## Definition of Done

- [ ] Sessions have `project` field in frontmatter
- [ ] Sessions have `narrative` field (improved summary)
- [ ] `projects/` folder with aggregated project notes
- [ ] `weekly/` folder with digest notes
- [ ] All tests pass with 90%+ coverage
- [ ] Run on real data, output is genuinely useful for humans
