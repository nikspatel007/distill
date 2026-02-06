---
status: done
priority: medium
workflow: null
---
# Build project_notes KPI measurer and implement ProjectNoteFormatter

In session-insights/src/session_insights/measurers/, create project_notes.py with a ProjectNotesMeasurer class inheriting from Measurer. It should: (1) check that the output projects/ folder exists, (2) verify it contains at least one note per detected project (excluding '(unknown)' and '(unassigned)'), (3) verify each note contains: timeline section, session count, and session links, (4) return KPIResult with name='project_notes', value=percentage of projects with valid notes, target=100. Then ensure the formatter generates proper project notes: in formatters/obsidian.py (or a new formatters/project_notes.py if obsidian.py is too large), implement or fix project note generation that aggregates sessions by project and outputs markdown with: Overview, Timeline (first/last session, total hours), Major Milestones (grouped by week), Key Decisions (extracted from session outcomes), and Related Sessions (linked). Wire this into the analysis pipeline in core.py so project notes are generated during `analyze`. Add unit tests.
