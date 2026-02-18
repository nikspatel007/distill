import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from distill.brainstorm.models import ContentCalendar, ContentIdea
from distill.brainstorm.publisher import publish_calendar


def _make_ideas() -> list[ContentIdea]:
    return [
        ContentIdea(
            title="Why Your Agent Evals Are Lying",
            angle="Most eval frameworks test the wrong thing",
            source_url="https://arxiv.org/abs/2026.55555",
            platform="both",
            rationale="Bridges evals and agents",
            pillars=["Evals and verification"],
            tags=["evals", "agents"],
        ),
        ContentIdea(
            title="The 3 Patterns Every AI Architect Needs",
            angle="Lessons from building production agent systems",
            source_url="https://example.com/patterns",
            platform="social",
            rationale="Architecture content",
            pillars=["AI architecture patterns"],
            tags=["architecture"],
        ),
    ]


def test_publish_saves_calendar_json(tmp_path):
    ideas = _make_ideas()
    publish_calendar(
        ideas=ideas,
        date="2026-02-17",
        output_dir=tmp_path,
        create_seeds=False,
        create_ghost_drafts=False,
    )
    cal_path = tmp_path / "content-calendar" / "2026-02-17.json"
    assert cal_path.exists()
    data = json.loads(cal_path.read_text())
    assert len(data["ideas"]) == 2


def test_publish_saves_calendar_markdown(tmp_path):
    ideas = _make_ideas()
    publish_calendar(
        ideas=ideas,
        date="2026-02-17",
        output_dir=tmp_path,
        create_seeds=False,
        create_ghost_drafts=False,
    )
    md_path = tmp_path / "content-calendar" / "2026-02-17.md"
    assert md_path.exists()
    content = md_path.read_text()
    assert "Agent Evals" in content
    assert "AI Architect" in content


def test_publish_creates_seeds(tmp_path):
    ideas = _make_ideas()
    seeds_path = tmp_path / ".distill-seeds.json"
    seeds_path.write_text('{"seeds": []}')

    with patch("distill.intake.seeds.SeedStore") as MockStore:
        mock_instance = MagicMock()
        MockStore.return_value = mock_instance

        publish_calendar(
            ideas=ideas,
            date="2026-02-17",
            output_dir=tmp_path,
            create_seeds=True,
            create_ghost_drafts=False,
        )

    assert mock_instance.add.call_count == 2


def test_publish_creates_ghost_drafts(tmp_path):
    ideas = _make_ideas()

    with patch("distill.integrations.ghost.GhostAPIClient") as MockGhost:
        mock_client = MagicMock()
        mock_client.create_post.return_value = {"id": "ghost-123"}
        MockGhost.return_value = mock_client

        with patch("distill.integrations.ghost.GhostConfig.from_env") as mock_env:
            mock_env.return_value = MagicMock(is_configured=True)

            publish_calendar(
                ideas=ideas,
                date="2026-02-17",
                output_dir=tmp_path,
                create_seeds=False,
                create_ghost_drafts=True,
            )

    # Only 1 idea has platform "both" (blog-eligible)
    assert mock_client.create_post.call_count == 1
