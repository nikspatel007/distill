---
status: pending
priority: medium
workflow: 
depends: ['add-parser-base-class', 'implement-cli-skeleton']
---

# Implement Claude session parser

Implement the first concrete parser for .claude/ directory. This proves the parser pattern works.

1. Create src/session_insights/parsers/claude.py:
   - ClaudeParser(BaseParser) that reads .claude/ directory
   - Handle JSON parsing with try/except for malformed files
   - Return list of SessionData objects
   - Log warnings for unparseable files (don't fail)

2. Update src/session_insights/cli.py analyze command:
   - Import ClaudeParser
   - When --dir is provided, look for .claude/ subdirectory
   - If found, parse and print count of sessions found

3. Create tests/test_claude_parser.py:
   - Test parsing valid session JSON
   - Test graceful handling of invalid JSON
   - Test empty directory returns empty list

SUCCESS CRITERIA: Running 'session-insights analyze --dir .' on a directory with .claude/ shows session count. Test coverage for claude.py >= 90%.
