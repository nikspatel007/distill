"""Backward-compat shim -- canonical location: distill.intake.services."""

from distill.intake.services import (  # noqa: F401
    _BATCH_SIZE,
    _INTELLIGENCE_MODEL,
    _build_classification_prompt,
    _build_entity_prompt,
    _build_topic_prompt,
    _parse_json_response,
    classify_items,
    extract_entities,
    extract_topics,
)
