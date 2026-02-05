---
status: pending
priority: medium
workflow: 
---

# Diagnose CLI Implementation Failures

Before attempting any new CLI work, investigate why prior 'implement-cli-skeleton' tasks failed. Check: (1) Does src/session_insights/ directory exist? (2) Are there import errors or missing dependencies? (3) Is there partial/broken CLI code that needs cleanup? (4) Review any error logs or test failures. Output a brief diagnostic report to docs/cli-diagnostic.md with findings and recommended fix approach.
