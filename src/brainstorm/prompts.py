"""LLM prompts for the brainstorm analyst."""

from __future__ import annotations


def get_analyst_prompt(
    research_json: str,
    pillars: list[str],
    journal_context: str,
    existing_seeds: list[str],
    published_titles: list[str],
) -> str:
    pillar_list = "\n".join(f"- {p}" for p in pillars)
    seed_list = "\n".join(f"- {s}" for s in existing_seeds[:10]) if existing_seeds else "(none)"
    published_list = (
        "\n".join(f"- {t}" for t in published_titles[:20]) if published_titles else "(none)"
    )

    return f"""You are a content strategist. Given today's research findings and the creator's context, propose 2-3 content ideas.

## Content Pillars (ALL ideas must connect to at least one)
{pillar_list}

## Today's Research Findings
{research_json}

## Creator's Recent Journal
{journal_context[:2000]}

## Existing Seed Ideas (DO NOT duplicate)
{seed_list}

## Already Published (DO NOT re-cover)
{published_list}

## Output Format
Return a JSON array of 2-3 content ideas. Each object:
{{
  "title": "Working title",
  "angle": "The specific hook or argument (1-2 sentences)",
  "source_url": "URL that inspired this idea",
  "platform": "blog" | "social" | "both",
  "rationale": "Why this matters to the audience (1 sentence)",
  "pillars": ["Which content pillar(s) this serves"],
  "tags": ["relevant", "topic", "tags"]
}}

Rules:
- Every idea MUST connect to at least one content pillar
- Prefer ideas that bridge multiple pillars
- Titles should be provocative, not generic
- Angles should be specific and opinionated
- Return ONLY the JSON array, no other text"""
