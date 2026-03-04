"""Tests for executive briefing model and persistence."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from distill.graph.briefing import (
    BRIEFING_FILENAME,
    Briefing,
    BriefingArea,
    BriefingLearning,
    BriefingRecommendation,
    BriefingRisk,
    BriefingSynthesisError,
    _load_recent_intake,
    _strip_json_fences,
    generate_briefing,
    load_briefing,
    save_briefing,
)
from distill.graph.prompts import get_briefing_prompt


def _sample_briefing() -> Briefing:
    return Briefing(
        date="2026-03-04",
        time_window_hours=48,
        summary="You made strong progress on TroopX workflows.",
        areas=[
            BriefingArea(
                name="TroopX",
                status="active",
                momentum="accelerating",
                headline="Workflow engine taking shape",
                sessions=8,
                reading_count=3,
                open_threads=["state machine edge cases"],
            )
        ],
        learning=[
            BriefingLearning(
                topic="Distributed state machines",
                reading_count=3,
                connection="Directly relevant to TroopX",
                status="emerging",
            )
        ],
        risks=[
            BriefingRisk(
                severity="high",
                headline="Registration module fragile",
                detail="Recurring problems growing",
                project="TroopX",
            )
        ],
        recommendations=[
            BriefingRecommendation(
                priority=1,
                action="Stabilize workflow registration",
                rationale="Unblocks safer iteration",
            )
        ],
    )


def test_briefing_model_defaults():
    b = Briefing()
    assert b.summary == ""
    assert b.areas == []
    assert b.time_window_hours == 48


def test_briefing_roundtrip(tmp_path: Path):
    original = _sample_briefing()
    save_briefing(original, tmp_path)

    loaded = load_briefing(tmp_path)
    assert loaded is not None
    assert loaded.summary == original.summary
    assert len(loaded.areas) == 1
    assert loaded.areas[0].name == "TroopX"
    assert loaded.areas[0].momentum == "accelerating"
    assert len(loaded.learning) == 1
    assert loaded.learning[0].topic == "Distributed state machines"
    assert len(loaded.risks) == 1
    assert loaded.risks[0].severity == "high"
    assert len(loaded.recommendations) == 1


def test_load_missing_file(tmp_path: Path):
    assert load_briefing(tmp_path) is None


def test_load_corrupt_file(tmp_path: Path):
    (tmp_path / BRIEFING_FILENAME).write_text("not json", encoding="utf-8")
    assert load_briefing(tmp_path) is None


def test_save_creates_directory(tmp_path: Path):
    nested = tmp_path / "deep" / "dir"
    save_briefing(_sample_briefing(), nested)
    assert (nested / BRIEFING_FILENAME).exists()


def test_briefing_area_status_values():
    for status in ("active", "cooling", "emerging"):
        a = BriefingArea(name="test", status=status)
        assert a.status == status


def test_briefing_area_momentum_values():
    for momentum in ("accelerating", "steady", "decelerating"):
        a = BriefingArea(name="test", momentum=momentum)
        assert a.momentum == momentum


# ── Prompt + generator tests ────────────────────────────────────────────


def test_get_briefing_prompt_contains_sections():
    data = {
        "project": "TroopX",
        "time_window_hours": 48,
        "sessions": [
            {
                "project": "TroopX",
                "goal": "Build workflow engine",
                "hours_ago": 2,
                "files_modified": ["a.py"],
                "problems": [{"error": "import error"}],
                "entities": ["python", "temporal"],
            },
        ],
        "top_entities": [{"name": "python", "count": 10}],
        "other_projects": [],
    }
    prompt = get_briefing_prompt(
        data, "2 error hotspots detected", "Read 3 articles on state machines"
    )
    assert "TroopX" in prompt
    assert "Build workflow engine" in prompt
    assert "Structural Insights" in prompt
    assert "Recent Reading" in prompt
    assert "valid JSON" in prompt


def test_get_briefing_prompt_empty_data():
    prompt = get_briefing_prompt(
        {"project": "(all)", "time_window_hours": 48, "sessions": []},
        "",
        "",
    )
    assert "Project: (all)" in prompt
    assert "Structural Insights" not in prompt
    assert "Recent Reading" not in prompt


def test_strip_json_fences():
    assert _strip_json_fences('```json\n{"a": 1}\n```') == '{"a": 1}'
    assert _strip_json_fences('{"a": 1}') == '{"a": 1}'
    assert _strip_json_fences('```\n{"a": 1}\n```') == '{"a": 1}'


def test_load_recent_intake_missing_dir(tmp_path: Path):
    assert _load_recent_intake(tmp_path) == ""


def test_load_recent_intake_reads_files(tmp_path: Path):
    intake_dir = tmp_path / "intake"
    intake_dir.mkdir()
    (intake_dir / "intake-2026-03-04.md").write_text(
        '---\ntags: [python, testing]\nhighlights:\n  - "Found a great article"'
        "\n---\n# Test Title\nBody text",
        encoding="utf-8",
    )
    result = _load_recent_intake(tmp_path)
    assert "intake-2026-03-04" in result
    assert "Test Title" in result
    assert "python, testing" in result


@patch("distill.graph.briefing.subprocess.run")
@patch("distill.graph.briefing.GraphStore")
@patch("distill.graph.briefing.GraphQuery")
@patch("distill.graph.briefing.GraphInsights")
def test_generate_briefing_success(
    mock_insights_cls, mock_query_cls, mock_store_cls, mock_run, tmp_path: Path
):
    mock_query = mock_query_cls.return_value
    mock_query.gather_context_data.return_value = {
        "project": "(all)",
        "time_window_hours": 48,
        "sessions": [],
        "top_entities": [],
        "active_files": [],
        "other_projects": [],
    }
    mock_insights = mock_insights_cls.return_value
    mock_insights.generate_daily_insights.return_value = MagicMock(
        coupling_clusters=[],
        error_hotspots=[],
        scope_warnings=[],
        recurring_problems=[],
        session_count=0,
        avg_files_per_session=0,
        total_problems=0,
    )

    mock_run.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps({
            "summary": "Good progress on TroopX.",
            "areas": [
                {
                    "name": "TroopX",
                    "status": "active",
                    "momentum": "accelerating",
                    "headline": "Workflow engine",
                    "sessions": 5,
                    "reading_count": 2,
                    "open_threads": [],
                }
            ],
            "learning": [],
            "risks": [],
            "recommendations": [
                {"priority": 1, "action": "Keep going", "rationale": "Momentum"}
            ],
        }),
        stderr="",
    )

    briefing = generate_briefing(tmp_path)
    assert briefing.summary == "Good progress on TroopX."
    assert len(briefing.areas) == 1
    assert briefing.areas[0].name == "TroopX"
    assert len(briefing.recommendations) == 1


@patch("distill.graph.briefing.subprocess.run")
@patch("distill.graph.briefing.GraphStore")
@patch("distill.graph.briefing.GraphQuery")
@patch("distill.graph.briefing.GraphInsights")
def test_generate_briefing_claude_not_found(
    mock_insights_cls, mock_query_cls, mock_store_cls, mock_run, tmp_path: Path
):
    mock_query_cls.return_value.gather_context_data.return_value = {
        "project": "(all)",
        "time_window_hours": 48,
        "sessions": [],
        "top_entities": [],
        "active_files": [],
        "other_projects": [],
    }
    mock_insights_cls.return_value.generate_daily_insights.return_value = MagicMock(
        coupling_clusters=[],
        error_hotspots=[],
        scope_warnings=[],
        recurring_problems=[],
        session_count=0,
        avg_files_per_session=0,
        total_problems=0,
    )
    mock_run.side_effect = FileNotFoundError("claude not found")
    with pytest.raises(BriefingSynthesisError, match="CLI not found"):
        generate_briefing(tmp_path)
