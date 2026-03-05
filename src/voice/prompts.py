"""LLM prompts for voice pattern extraction."""

from __future__ import annotations


def get_extraction_prompt() -> str:
    """Return the system prompt for extracting voice rules from chat history."""
    return """\
You are analyzing a conversation between a user and an AI writing assistant.
The user edited AI-generated content and gave feedback about style, tone, and word choice.

Extract voice rules from this conversation. Each rule should be:
- A specific, actionable instruction (not vague like "write better")
- Grounded in what the user actually said or changed
- Categorized as one of: tone, specificity, structure, vocabulary, framing

Categories:
- tone: Formality level, hedging, confidence, humor
- specificity: Concrete vs abstract, naming things, metrics
- structure: Sentence length, paragraph rhythm, transitions
- vocabulary: Preferred/avoided words, jargon policy
- framing: How setbacks are described, how wins are shared

Return ONLY valid JSON — no markdown fences, no commentary. Format:
[
  {
    "rule": "Imperative instruction (e.g., 'Use direct statements')",
    "category": "tone|specificity|structure|vocabulary|framing",
    "examples": {"before": "original text", "after": "edited text"}
  }
]

Rules:
- Only extract rules with clear evidence in the conversation.
- Do NOT extract content-specific preferences (topic choices, what to cover).
- ONLY extract style/voice patterns (HOW to write, not WHAT to write).
- If there are no clear style patterns, return an empty array: []
"""
