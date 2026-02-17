import json
from distill.brainstorm.models import (
    ContentIdea, ContentCalendar, ResearchItem, SourceTier,
    load_calendar, save_calendar,
)


def test_source_tier_values():
    assert SourceTier.MANUAL == "manual"
    assert SourceTier.HN == "hacker_news"
    assert SourceTier.ARXIV == "arxiv"
    assert SourceTier.FOLLOWED == "followed"


def test_research_item_creation():
    item = ResearchItem(
        title="Test Paper",
        url="https://example.com/paper",
        summary="A test paper about agents.",
        source_tier=SourceTier.ARXIV,
    )
    assert item.title == "Test Paper"
    assert item.source_tier == SourceTier.ARXIV
    assert item.points is None


def test_content_idea_creation():
    idea = ContentIdea(
        title="Building Reliable Agent Swarms",
        angle="How evals catch coordination failures before production",
        source_url="https://arxiv.org/abs/2026.12345",
        platform="both",
        rationale="Bridges multi-agent and evals pillars",
        pillars=["Building multi-agent systems", "Evals and verification"],
        tags=["agents", "evals"],
    )
    assert idea.platform == "both"
    assert len(idea.pillars) == 2
    assert idea.status == "pending"


def test_content_calendar_serialization():
    cal = ContentCalendar(
        date="2026-02-17",
        ideas=[
            ContentIdea(
                title="Test",
                angle="Test angle",
                source_url="https://example.com",
                platform="blog",
                rationale="Test",
                pillars=["AI architecture patterns"],
            )
        ],
    )
    data = json.loads(cal.model_dump_json())
    assert data["date"] == "2026-02-17"
    assert len(data["ideas"]) == 1
    assert data["ideas"][0]["status"] == "pending"


def test_content_calendar_load_save(tmp_path):
    cal = ContentCalendar(
        date="2026-02-17",
        ideas=[
            ContentIdea(
                title="Test",
                angle="Angle",
                source_url="https://example.com",
                platform="social",
                rationale="Reason",
                pillars=["Human-AI collaboration"],
            )
        ],
    )
    save_calendar(cal, tmp_path)
    loaded = load_calendar("2026-02-17", tmp_path)
    assert loaded is not None
    assert len(loaded.ideas) == 1
    assert loaded.ideas[0].title == "Test"


def test_load_calendar_missing(tmp_path):
    loaded = load_calendar("2099-01-01", tmp_path)
    assert loaded is None
