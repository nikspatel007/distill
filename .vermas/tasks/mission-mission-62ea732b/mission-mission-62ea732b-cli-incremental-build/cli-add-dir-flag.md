---
status: done
priority: medium
workflow: null
---
# Add --dir Flag to Analyze Subcommand

Extend the analyze subcommand to accept --dir flag: (1) Add --dir argument with default='.' (2) Validate the directory exists (3) Print confirmation: 'Analyzing directory: {dir}'. Test with: session-insights analyze --dir . This is ONE atomic change only.
