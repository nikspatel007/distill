# Detailed Merge Conflict Risk Analysis

## Executive Summary

**HIGH-RISK CONFLICTS:** 2 files
- `src/session_insights/cli.py` (Branches 3 & 5)
- `src/session_insights/formatters/obsidian.py` (Branches 1 & 4)

**CONFLICT LIKELIHOOD:** Very High - Both files have substantial overlapping changes

---

## File-by-File Analysis

### 1. `src/session_insights/cli.py` - CRITICAL CONFLICT

**Branches:** 3 (implement-analyze-subcommand) & 5 (wire-cli-to-existing-parsers)

#### Branch 3 Changes:
- Adds contextlib import
- Adds new imports: `compute_field_coverage`, `compute_richness_score`
- Adds `_stderr_console` and `_progress_context()` helper
- Adds 6 new functions:
  - `_empty_stats_json()` (14 lines)
  - `_build_stats_json()` (30 lines)
  - `_infer_source_from_path()` (13 lines)
  - `_parse_single_file()` (24 lines+)
  - Plus `analyze` subcommand implementation
- **Total additions: ~548 LOC (new analyze subcommand)**

#### Branch 5 Changes:
- Removes imports: `ClaudeParser`, `CodexParser`
- Adds import: `parse_sessions`
- Refactors `sessions_cmd()` to use new `discover_sessions()` + `parse_sessions()` API
- Changes from hardcoded parser instantiation to generic discovery
- **Total modifications: ~50 LOC (refactor of existing command)**

#### Conflict Analysis:
**TYPE:** Semantic merge + structural

**Key Issues:**
1. **Import conflict:** Branch 3 adds many imports; Branch 5 removes parsers. Need to merge both selectively.
2. **Locations matter:**
   - Branch 3 adds functions AFTER the existing `_generate_index()` 
   - Branch 5 modifies `sessions_cmd()` which is in the middle of the file
   - Both likely touch the import section differently
3. **No direct line conflicts** in the visible diffs, BUT:
   - If Branch 5 is merged first, then Branch 3's new analyze command won't have access to certain utilities
   - If Branch 3 is merged first, then Branch 5's refactored `sessions_cmd()` will need to work with the new structure

**RESOLUTION STRATEGY:**
- Merge in order: **Branch 5 first** (simpler refactor), then **Branch 3** (adds new functionality)
- OR manually integrate both changes ensuring:
  - Branch 5's parser imports are removed
  - Branch 3's new functions are present
  - Both branches' core.py imports are correct

---

### 2. `src/session_insights/formatters/obsidian.py` - CRITICAL CONFLICT

**Branches:** 1 (formatter-vermas-rich-rendering) & 4 (formatter-vermas-and-content-rendering)

#### Branch 1 Changes:
- Adds `timedelta` import
- Adds helper function `_format_timedelta()` (16 lines)
- Completely rewrites `_format_conversation_section()` with:
  - New subsections: User Questions, Tool Usage, Key Decisions, Accomplishments
  - Adds 4 new helper methods:
    - `_extract_user_questions()`
    - `_format_tool_usage_analysis()`
    - `_extract_key_decisions()`
    - `_format_accomplishments()`
  - **Total: +180 LOC**
- Focuses on **rich conversation analysis** with multiple subsections

#### Branch 4 Changes:
- Modifies `_format_session_body()` to handle VerMAS-specific fields:
  - Uses `task_name` for title when available
  - Uses `task_description` for summary when available
- Completely rewrites `_format_conversation_section()` with different approach:
  - New subsections: "What Was Asked", "Tool Usage Summary", "Accomplishments", "Key Decisions"
  - Adds helper `_infer_tool_purpose()`
  - Adds helper `_extract_key_decisions()`
  - **Total: +100+ LOC**
- Focuses on **VerMAS session metadata** + structured conversation

#### Conflict Analysis:
**TYPE:** Direct line conflicts + semantic conflict

**Key Issues:**
1. **Both rewrite the same method** (`_format_conversation_section()`) from scratch
   - Lines will definitely conflict
   - Both have similar intent (subsections) but different implementation
   - Branch 1: 4 subsections (questions, tools, decisions, accomplishments)
   - Branch 4: 4 subsections (what was asked, tool usage, accomplishments, decisions)
   - Overlap but not identical

2. **Helper method conflicts:**
   - Both add `_extract_key_decisions()` - likely IDENTICAL or very similar
   - May conflict on implementation details

3. **Scope differences:**
   - Branch 4 modifies `_format_session_body()` (new code in Branch 1)
   - Branch 1 only touches the conversation section
   - Branch 4 touches both session body AND conversation section

**CONFLICT LIKELIHOOD:** 95%+ - Direct overlapping rewrites

**RESOLUTION STRATEGY:**
- **CANNOT easily auto-merge** - requires manual integration
- Option A: Merge Branch 4 first (VerMAS enhancements + conversation rewrite), then manually integrate Branch 1's conversation improvements
- Option B: Merge Branch 1 first, then cherry-pick Branch 4's VerMAS-specific enhancements and tool purpose logic
- **RECOMMENDED:** Manual merge combining both approaches:
  - Use Branch 4's VerMAS session body enhancements
  - Use Branch 4's "What Was Asked" + "Tool Usage Summary" subsections
  - Add Branch 1's "_format_timedelta()" helper
  - Add Branch 1's richer accomplishments formatting

---

### 3. `tests/formatters/test_obsidian.py` - MEDIUM CONFLICT

**Branches:** 1 & 4

**CONFLICT LIKELIHOOD:** 50-70% - Tests for overlapping functionality

---

## Merge Order Recommendation

### **RECOMMENDED ORDER: 2 → 4 → 5 → 3**

Rationale:
1. **Merge #2** (integration-tests): No conflicts, safe to merge first
2. **Merge #4** (formatter-vermas-and-content): Takes precedence because it adds VerMAS-specific features
3. **Merge #5** (wire-cli): Simpler refactor, prepares for Branch 3's analyze command
4. **Merge #3** (implement-analyze-subcommand): Most complex, benefits from having the other infrastructure merged first

### For the Critical Conflicts:

**obsidian.py (Branches 1 & 4):**
- After merging #4, manually integrate Branch 1's `_format_timedelta()` and richer formatting
- OR declare Branch 4 the "winner" and recreate Branch 1's improvements manually in a follow-up

**cli.py (Branches 3 & 5):**
- Merge #5 first (simpler)
- Merge #3 second (adds new commands - should not directly conflict with refactored sessions_cmd)

---

## File Impact Summary

| File | Branch 1 | Branch 2 | Branch 3 | Branch 4 | Branch 5 | Conflict Risk |
|------|----------|----------|----------|----------|----------|------------------|
| cli.py | - | - | ✓ (+548) | - | ✓ (~50) | CRITICAL |
| obsidian.py | ✓ (+180) | - | - | ✓ (+100) | - | CRITICAL |
| test_obsidian.py | ✓ | - | - | ✓ | - | MEDIUM |
| core.py | - | - | ✓ | - | - | LOW |
| pyproject.toml | - | ✓ | - | - | - | LOW |
| test_full_pipeline.py | - | ✓ | - | - | - | LOW |
| test_cli_e2e.py | - | - | ✓ | - | - | LOW |
| test_cli_wiring.py | - | - | - | - | ✓ | LOW |
| test_cli.py | - | - | ✓ | - | - | LOW |
| test_core_stats.py | - | - | ✓ | - | - | LOW |

**Total unmerged code: ~2,517 LOC**
- Branch 1: +476 LOC (obsidian.py)
- Branch 2: ~20 LOC (tests only)
- Branch 3: +548 LOC (cli.py + core.py + tests)
- Branch 4: +375 LOC (formatters + tests)
- Branch 5: +269 LOC (cli.py + tests)

