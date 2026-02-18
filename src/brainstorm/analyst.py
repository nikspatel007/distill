"""Backward-compat shim -- re-exports analyst logic from services."""

from distill.brainstorm.services import (  # noqa: F401
    _call_llm,
    _strip_json_fences,
    analyze_research,
    score_against_pillars,
)
