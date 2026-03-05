"""Voice extraction and merging logic."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from distill.content.models import ContentRecord
from distill.content.store import ContentStore
from distill.voice.models import RuleCategory, VoiceProfile, VoiceRule
from distill.voice.prompts import get_extraction_prompt
from distill.voice.store import load_voice_profile, save_voice_profile

logger = logging.getLogger(__name__)


def compute_confidence(source_count: int) -> float:
    """Compute confidence from number of confirming sources."""
    if source_count >= 6:
        return 0.9
    if source_count >= 3:
        return 0.6
    return 0.3


def merge_rule_into_profile(
    profile: VoiceProfile,
    new_rule: VoiceRule | None = None,
    *,
    is_match_id: str | None = None,
    contradict_id: str | None = None,
) -> None:
    """Merge a new rule into the profile, or apply a contradiction.

    - is_match_id: ID of existing rule that matches new_rule (reinforce).
    - contradict_id: ID of existing rule that is contradicted (decay).
    - If neither, new_rule is appended as a new entry.
    """
    if contradict_id:
        for r in profile.rules:
            if r.id == contradict_id:
                r.confidence = round(r.confidence / 2, 2)
                return
        return

    if new_rule is None:
        return

    if is_match_id:
        for r in profile.rules:
            if r.id == is_match_id:
                r.source_count += 1
                r.confidence = compute_confidence(r.source_count)
                if new_rule.examples and not r.examples:
                    r.examples = new_rule.examples
                return
        return

    # New rule — append
    profile.rules.append(new_rule)


def _parse_extraction_response(raw: str) -> list[dict]:
    """Parse the LLM extraction response into a list of rule dicts."""
    from distill.shared.llm import strip_json_fences

    cleaned = strip_json_fences(raw)
    try:
        data = json.loads(cleaned)
        if isinstance(data, list):
            return data
    except (json.JSONDecodeError, ValueError):
        logger.warning("Failed to parse voice extraction response")
    return []


def _dict_to_rule(d: dict) -> VoiceRule | None:
    """Convert an extraction response dict to a VoiceRule."""
    rule_text = d.get("rule", "").strip()
    cat_str = d.get("category", "").strip().lower()
    if not rule_text or not cat_str:
        return None
    try:
        category = RuleCategory(cat_str)
    except ValueError:
        return None
    examples = d.get("examples")
    if isinstance(examples, dict) and "before" in examples and "after" in examples:
        examples = {"before": str(examples["before"]), "after": str(examples["after"])}
    else:
        examples = None
    return VoiceRule(rule=rule_text, category=category, examples=examples)


def extract_from_record(record: ContentRecord) -> list[VoiceRule]:
    """Extract voice rules from a single ContentRecord's chat history.

    Makes an LLM call to analyze the chat and extract style patterns.
    """
    from distill.shared.llm import LLMError, call_claude

    if len(record.chat_history) < 2:
        return []

    # Format chat history for the LLM
    chat_text = "\n".join(f"[{msg.role}]: {msg.content}" for msg in record.chat_history)

    system_prompt = get_extraction_prompt()
    user_prompt = f"Analyze this editing conversation and extract voice/style rules:\n\n{chat_text}"

    try:
        raw = call_claude(
            system_prompt,
            user_prompt,
            model="haiku",
            timeout=60,
            label=f"voice-extract:{record.slug}",
        )
    except LLMError as exc:
        logger.warning("Voice extraction failed for %s: %s", record.slug, exc)
        return []

    parsed = _parse_extraction_response(raw)
    rules = []
    for d in parsed:
        rule = _dict_to_rule(d)
        if rule:
            rules.append(rule)
    return rules


def extract_voice_rules(output_dir: Path) -> VoiceProfile:
    """Extract voice rules from all unprocessed ContentStore records.

    Loads the ContentStore and voice profile, finds records with chat history
    that haven't been processed yet, extracts rules from each, merges them
    into the profile, and saves.
    """
    store = ContentStore(output_dir)
    profile = load_voice_profile(output_dir)

    all_records = store.list()
    unprocessed = [
        r for r in all_records if r.slug not in profile.processed_slugs and len(r.chat_history) >= 2
    ]

    if not unprocessed:
        logger.info("No unprocessed records with chat history")
        return profile

    total_new = 0
    for record in unprocessed:
        new_rules = extract_from_record(record)
        for rule in new_rules:
            merge_rule_into_profile(profile, rule)
            total_new += 1
        profile.processed_slugs.append(record.slug)

    profile.extracted_from = len(profile.processed_slugs)
    profile.last_updated = datetime.now(tz=UTC)
    profile.prune()
    save_voice_profile(profile, output_dir)

    logger.info(
        "Extracted %d new rules from %d records (total: %d rules)",
        total_new,
        len(unprocessed),
        len(profile.rules),
    )
    return profile
