# Executive Briefing — Knowledge Graph Intelligence Layer

## Problem

The Knowledge Graph dashboard shows developer telemetry — session IDs, file paths, problem counts. An executive (even a solo founder who is also the builder) wants actionable intelligence: where is my attention, what's at risk, what should I focus on, and how does my reading connect to my building.

## Solution

An LLM-synthesized daily briefing that answers:
1. Where is my attention and which way is it moving?
2. What's at risk?
3. What should I focus on today?
4. How does my reading connect to my work?

Pre-computed during the daily pipeline run. Instant page load. Saved as `.distill-briefing.json`.

## Audience

Solo founder / indie dev who is both builder and decision-maker. Language is second-person ("You made progress on..."), plain English (no file paths or jargon), but a non-technical stakeholder could also read it.

## Data Model — `.distill-briefing.json`

```json
{
  "date": "2026-03-04",
  "generated_at": "2026-03-04T06:15:00Z",
  "time_window_hours": 48,
  "summary": "You made strong progress on TroopX workflows and dove deep into Temporal orchestration patterns...",
  "areas": [
    {
      "name": "TroopX",
      "status": "active",
      "momentum": "accelerating",
      "headline": "Workflow engine taking shape — state machine and activity types landed",
      "sessions": 8,
      "reading_count": 3,
      "open_threads": ["state machine edge cases", "activity registration"]
    }
  ],
  "learning": [
    {
      "topic": "Distributed state machines",
      "reading_count": 3,
      "connection": "Directly relevant to TroopX's state machine module",
      "status": "emerging"
    }
  ],
  "risks": [
    {
      "severity": "high",
      "headline": "Workflow registration is becoming fragile",
      "detail": "Recurring problems concentrating in registration module. Error count growing week over week.",
      "project": "TroopX"
    }
  ],
  "recommendations": [
    {
      "priority": 1,
      "action": "Stabilize the workflow registration module before adding new activity types",
      "rationale": "Recurring problems are growing — fixing this unblocks safer iteration"
    }
  ]
}
```

### Status vocabulary

- **active** — spending time here (sessions or reading this period)
- **cooling** — attention has drifted away (was active last period, quiet now)
- **emerging** — brand new area, first appeared in last 48h

### Momentum vocabulary

- **accelerating** — more activity than last period
- **steady** — similar activity level
- **decelerating** — less activity than last period

No completion percentages. No "done." Momentum relative to yourself.

## Pipeline Integration

Runs during daily pipeline, after graph insights:

1. `distill graph build` — extracts sessions into graph (exists)
2. `distill graph insights` — generates DailyInsights (exists)
3. `distill graph briefing` — NEW: synthesizes executive briefing

### Data inputs to the LLM prompt

1. **Graph data** — `GraphQuery.gather_context_data()`: recent sessions, projects, entities, problems, goals
2. **Insights data** — `GraphInsights.generate_daily_insights()`: coupling clusters, error hotspots, scope warnings, recurring problems
3. **Intake data** — latest intake digest entries: what user has been reading, topics, sources

### Prompt design

The system prompt instructs Claude to:
- Write in second person ("You made progress on...")
- Use momentum language (active/cooling/emerging), never completion language
- Connect reading to building ("You're reading about X while working on X")
- Surface unresolved threads, not just activity counts
- Keep it plain English — no file paths, no session IDs
- Limit recommendations to top 3, ordered by impact
- Output valid JSON matching the briefing schema

The key value: connecting dots across domains that heuristics can't. Reading patterns + building patterns + risk signals = personalized intelligence.

## Frontend — Briefing Tab

New default landing tab on the Graph page. Tab order: **Briefing** | Activity | Explorer | Insights

### Layout

**Summary** — 2-3 sentence narrative in larger text. The 5-second TL;DR. Subtle timestamp ("Generated this morning at 6:15 AM").

**Areas** — Card per project/area with activity. Color accent by status (green = active, amber = cooling, blue = emerging). Shows name, headline, momentum direction, session count, reading count, open threads.

**Learning** — Cards showing topics from reading. How they connect to active work. Status badge (active/emerging/cooling).

**Risks & Recommendations** — Combined section. Risk context feeds into numbered recommendations. Red accent for high severity, amber for medium. Each recommendation has bold action + lighter rationale.

## Files

| File | Change |
|------|--------|
| `src/graph/briefing.py` | **New** — BriefingGenerator class, prompt, JSON parsing |
| `src/graph/prompts.py` | Add executive briefing system/user prompts |
| `src/graph/__init__.py` | Export BriefingGenerator |
| `src/cli.py` | Add `distill graph briefing` command |
| `src/pipeline/intake.py` | Add briefing step after graph insights |
| `web/shared/schemas.ts` | Add briefing Zod schemas |
| `web/server/routes/graph.ts` | Add `GET /api/graph/briefing` endpoint |
| `web/src/routes/graph.tsx` | Add Briefing tab (default), restructure tab order |
| `tests/graph/test_briefing.py` | **New** — Python tests |
| `web/server/__tests__/graph.test.ts` | Add briefing endpoint test |
