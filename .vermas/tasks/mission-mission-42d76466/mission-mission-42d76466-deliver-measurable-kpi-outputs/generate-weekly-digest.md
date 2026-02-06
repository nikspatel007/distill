---
status: pending
priority: medium
workflow: 
---

# Generate weekly digest for the most recent complete week

Implement a weekly digest generator that groups sessions by ISO week and produces a human-readable markdown summary. For the most recent complete week: 1) Group all sessions in that week by project. 2) Summarize 'What Got Done' by extracting outcomes and summaries from each session. 3) Summarize 'Challenges Faced' by looking for sessions tagged #debugging or #fix or with long durations. 4) List 'Key Stats' (total sessions, total hours, files modified, commands run). 5) Write the digest to the output vault as a weekly note. This directly targets the weekly_digests KPI which is furthest from target. Print the number of digests generated and a quality self-assessment.
