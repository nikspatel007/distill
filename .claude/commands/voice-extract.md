---
description: "Extract voice patterns from Studio chat histories and update the voice profile. Run after editing posts in Studio, or periodically to keep the profile fresh."
---

Invoke the voice-memory skill in Extract mode. Read the skill at .claude/skills/voice-memory/SKILL.md and follow Mode 1: Extract Voice Patterns exactly. Load the ContentStore, find unprocessed chat histories, extract voice rules via LLM, merge with existing profile, and save to .distill-voice.json.
