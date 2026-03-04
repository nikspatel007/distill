"""Tests for executive briefing model and persistence."""

import json
from pathlib import Path

import pytest

from distill.graph.briefing import (
    BRIEFING_FILENAME,
    Briefing,
    BriefingArea,
    BriefingLearning,
    BriefingRecommendation,
    BriefingRisk,
    load_briefing,
    save_briefing,
)


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
