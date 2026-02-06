---
status: pending
priority: medium
workflow: 
---

# Generate project notes for top 3 projects from real session data

Using the project detection output from the previous task, generate project notes (markdown files) for the top 3 projects by session count. Each project note should follow the target format from the mission: project overview, timeline (start date, session count, total time), major milestones extracted from session summaries and tags, key decisions (extracted from sessions tagged #architecture or #decision or containing 'chose'/'decided' keywords), and a list of related sessions with wikilinks. Write these to the output vault directory. This directly targets the project_notes KPI (0% -> measurable). Also compute and print narrative_quality as a self-assessment score based on: does the note have all required sections (overview, timeline, milestones, decisions, related sessions)? Score = sections_present / total_sections * 100.
