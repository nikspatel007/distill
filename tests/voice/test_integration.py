"""Integration test — mock LLM extraction end-to-end."""

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from distill.content.models import ChatMessage, ContentRecord, ContentStatus, ContentType
from distill.content.store import ContentStore
from distill.voice.services import extract_voice_rules
from distill.voice.store import load_voice_profile


def _make_record(slug: str, messages: list[dict]) -> ContentRecord:
    return ContentRecord(
        slug=slug,
        content_type=ContentType.WEEKLY,
        title=f"Test post {slug}",
        body="Some content",
        status=ContentStatus.DRAFT,
        created_at=datetime.now(tz=UTC),
        chat_history=[
            ChatMessage(
                role=m["role"],
                content=m["content"],
                timestamp="2026-03-04T10:00:00Z",
            )
            for m in messages
        ],
    )


MOCK_LLM_RESPONSE = json.dumps([
    {
        "rule": "Use direct statements without hedging",
        "category": "tone",
        "examples": {"before": "This might work", "after": "This works"},
    },
    {
        "rule": "Name specific tools and versions",
        "category": "specificity",
        "examples": {"before": "the library", "after": "React 19"},
    },
])


@patch("distill.shared.llm.call_claude", return_value=MOCK_LLM_RESPONSE)
def test_end_to_end_extraction(mock_claude, tmp_path: Path):
    # Set up ContentStore with a record that has chat history (>= 2 messages)
    store = ContentStore(tmp_path)
    record = _make_record("test-post-1", [
        {"role": "user", "content": "This is too formal, make it more direct"},
        {"role": "assistant", "content": "I've updated the post to be more direct."},
    ])
    store.upsert(record)

    # Run extraction
    profile = extract_voice_rules(tmp_path)

    # Verify rules were extracted
    assert len(profile.rules) == 2
    assert profile.processed_slugs == ["test-post-1"]
    assert profile.extracted_from == 1

    # Verify rules are correct
    tone_rules = [r for r in profile.rules if r.category == "tone"]
    assert len(tone_rules) == 1
    assert "direct" in tone_rules[0].rule.lower()

    # Verify profile was saved to disk
    loaded = load_voice_profile(tmp_path)
    assert len(loaded.rules) == 2

    # Run again — should skip already-processed records
    profile2 = extract_voice_rules(tmp_path)
    assert len(profile2.rules) == 2  # No new rules added
    mock_claude.assert_called_once()  # Only 1 LLM call total


@patch("distill.shared.llm.call_claude", return_value=MOCK_LLM_RESPONSE)
def test_extraction_skips_records_without_chat(mock_claude, tmp_path: Path):
    store = ContentStore(tmp_path)
    # Only 1 message — below the threshold of 2 required by extract_from_record
    record = _make_record("no-chat", [
        {"role": "user", "content": "A single message"},
    ])
    store.upsert(record)

    profile = extract_voice_rules(tmp_path)
    assert len(profile.rules) == 0
    mock_claude.assert_not_called()


@patch("distill.shared.llm.call_claude", return_value=MOCK_LLM_RESPONSE)
def test_extraction_skips_empty_chat_history(mock_claude, tmp_path: Path):
    store = ContentStore(tmp_path)
    record = _make_record("empty-chat", [])
    store.upsert(record)

    profile = extract_voice_rules(tmp_path)
    assert len(profile.rules) == 0
    mock_claude.assert_not_called()
