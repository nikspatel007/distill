import json
from unittest.mock import patch

from distill.brainstorm.analyst import analyze_research, score_against_pillars
from distill.brainstorm.models import ContentIdea, ResearchItem, SourceTier


PILLARS = [
    "Building multi-agent systems",
    "AI architecture patterns",
    "Evals and verification",
]


def test_score_against_pillars_matches():
    items = [
        ResearchItem(
            title="Multi-Agent Coordination Framework",
            url="https://example.com/1",
            summary="A framework for coordinating multiple AI agents in production.",
            source_tier=SourceTier.ARXIV,
        ),
        ResearchItem(
            title="Best Pizza in NYC",
            url="https://example.com/2",
            summary="A review of pizza restaurants.",
            source_tier=SourceTier.HN,
        ),
    ]
    scored = score_against_pillars(items, PILLARS)
    assert len(scored) >= 1
    assert any("agent" in item.title.lower() for item in scored)


def test_analyze_research_returns_ideas():
    items = [
        ResearchItem(
            title="New Eval Framework for LLM Agents",
            url="https://arxiv.org/abs/2026.55555",
            summary="A comprehensive evaluation framework.",
            source_tier=SourceTier.ARXIV,
        ),
    ]

    llm_response = json.dumps([
        {
            "title": "Why Your Agent Evals Are Lying to You",
            "angle": "Most eval frameworks test the wrong thing",
            "source_url": "https://arxiv.org/abs/2026.55555",
            "platform": "both",
            "rationale": "Bridges evals and multi-agent pillars",
            "pillars": ["Evals and verification"],
            "tags": ["evals", "agents"],
        }
    ])

    with patch("distill.brainstorm.services._call_llm", return_value=llm_response):
        ideas = analyze_research(
            items=items,
            pillars=PILLARS,
            journal_context="Today I worked on agent evaluation.",
            existing_seeds=[],
            published_titles=[],
        )

    assert len(ideas) == 1
    assert ideas[0].title == "Why Your Agent Evals Are Lying to You"
    assert ideas[0].status == "pending"


def test_analyze_research_handles_bad_llm_response():
    items = [
        ResearchItem(
            title="Test",
            url="https://example.com",
            summary="Test",
            source_tier=SourceTier.HN,
        ),
    ]

    with patch("distill.brainstorm.services._call_llm", return_value="not json"):
        ideas = analyze_research(
            items=items,
            pillars=PILLARS,
            journal_context="",
            existing_seeds=[],
            published_titles=[],
        )

    assert ideas == []
