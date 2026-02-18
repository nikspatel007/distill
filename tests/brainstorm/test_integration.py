"""Integration test: full brainstorm pipeline with mocked sources."""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from distill.brainstorm.models import ResearchItem, SourceTier, load_calendar
from distill.brainstorm.sources import fetch_hacker_news
from distill.brainstorm.analyst import analyze_research
from distill.brainstorm.publisher import publish_calendar


def test_full_pipeline(tmp_path):
    """End-to-end: gather -> analyze -> publish."""
    # 1. Mock research items
    items = [
        ResearchItem(
            title="Multi-Agent Eval Framework",
            url="https://arxiv.org/abs/2026.12345",
            summary="A framework for evaluating multi-agent systems",
            source_tier=SourceTier.ARXIV,
            authors=["Alice"],
        ),
        ResearchItem(
            title="Building AI Teams That Actually Work",
            url="https://simonwillison.net/2026/teams",
            summary="Lessons from deploying agent teams",
            source_tier=SourceTier.FOLLOWED,
        ),
    ]

    pillars = [
        "Building multi-agent systems",
        "Evals and verification",
    ]

    # 2. Mock LLM response
    llm_response = json.dumps([
        {
            "title": "Your Agent Team Is Only as Good as Your Evals",
            "angle": "Why eval-first development matters for multi-agent systems",
            "source_url": "https://arxiv.org/abs/2026.12345",
            "platform": "both",
            "rationale": "Bridges the two most important pillars",
            "pillars": ["Building multi-agent systems", "Evals and verification"],
            "tags": ["agents", "evals", "testing"],
        },
    ])

    # 3. Analyze
    with patch("distill.brainstorm.services._call_llm", return_value=llm_response):
        ideas = analyze_research(
            items=items,
            pillars=pillars,
            journal_context="Today I worked on agent coordination.",
            existing_seeds=[],
            published_titles=[],
        )

    assert len(ideas) == 1

    # 4. Publish (no Ghost, no seeds -- just calendar files)
    calendar = publish_calendar(
        ideas=ideas,
        date="2026-02-17",
        output_dir=tmp_path,
        create_seeds=False,
        create_ghost_drafts=False,
    )

    # 5. Verify outputs
    assert (tmp_path / "content-calendar" / "2026-02-17.json").exists()
    assert (tmp_path / "content-calendar" / "2026-02-17.md").exists()

    loaded = load_calendar("2026-02-17", tmp_path)
    assert loaded is not None
    assert len(loaded.ideas) == 1
    assert loaded.ideas[0].title == "Your Agent Team Is Only as Good as Your Evals"
    assert "Evals and verification" in loaded.ideas[0].pillars
