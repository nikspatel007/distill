---
status: pending
priority: medium
workflow: 
---

# Build narrative_quality KPI measurer and implement narrative generation

In session-insights/src/session_insights/measurers/, create narrative_quality.py with a NarrativeQualityMeasurer class inheriting from Measurer. It should: (1) load all parsed sessions, (2) for each session check that `narrative` is non-empty, longer than 10 words, and differs from the raw `summary` field, (3) return a KPIResult with name='narrative_quality', value=percentage passing, target=80. Then implement narrative generation: in parsers/claude.py and parsers/vermas.py, after parsing a session, construct a human-readable narrative string by combining: the summary (cleaned up), key outcomes, primary tools used, and tags into a coherent 1-2 sentence description. Set BaseSession.narrative to this constructed string. Example: 'Debugged timezone handling in session-insights parsers, modifying 3 files with focus on datetime normalization. Tagged: #debugging #bugfix'. Add unit tests for both the measurer and narrative generation logic.
