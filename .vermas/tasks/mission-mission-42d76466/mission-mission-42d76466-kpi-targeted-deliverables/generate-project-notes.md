---
status: done
priority: medium
workflow: null
---
# Generate project aggregation notes per detected project

Using the project detection from the previous task, implement a command or module that generates one markdown note per detected project in a `projects/` output folder. Each note should contain: project name, overview (derived from session summaries), timeline (first/last session dates), session count, total time, major milestones (cluster sessions by week and summarize), key decisions (extract from session summaries mentioning 'chose', 'decided', 'switched to'), and a list of related sessions as wiki-links (`[[session-id]]`). The output format must match the mission spec. Add a test that verifies at least one project note is generated correctly. This directly delivers Mission Deliverable #1 (Project Notes) and moves the `project_notes` KPI.
