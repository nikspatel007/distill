"""Tests for project_detection KPI measurer."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from distill.measurers.base import KPIResult
from distill.measurers.project_detection import ProjectDetectionMeasurer
from distill.parsers.models import BaseSession


def _make_session(project: str = "") -> BaseSession:
    return BaseSession(
        session_id="s1",
        start_time=datetime(2024, 6, 10, 10, 0, tzinfo=timezone.utc),
        end_time=datetime(2024, 6, 10, 11, 0, tzinfo=timezone.utc),
        duration_seconds=3600,
        num_turns=5,
        project=project,
        source="claude",
    )


class TestProjectDetectionMeasurer:
    def test_result_type(self) -> None:
        measurer = ProjectDetectionMeasurer()
        result = measurer.measure()
        assert isinstance(result, KPIResult)
        assert result.kpi == "project_detection"

    def test_target_is_80(self) -> None:
        assert ProjectDetectionMeasurer.TARGET == 80.0

    def test_measure_from_sessions_all_detected(self) -> None:
        sessions = [_make_session("my-app"), _make_session("other-app")]
        result = ProjectDetectionMeasurer().measure_from_sessions(sessions)
        assert result.value == 100.0
        assert result.details["with_project"] == 2

    def test_measure_from_sessions_none_detected(self) -> None:
        sessions = [_make_session(""), _make_session("")]
        result = ProjectDetectionMeasurer().measure_from_sessions(sessions)
        assert result.value == 0.0
        assert result.details["without_project"] == 2

    def test_measure_from_sessions_partial(self) -> None:
        sessions = [_make_session("app"), _make_session(""), _make_session(""), _make_session("")]
        result = ProjectDetectionMeasurer().measure_from_sessions(sessions)
        assert result.value == 25.0

    def test_measure_from_sessions_empty(self) -> None:
        result = ProjectDetectionMeasurer().measure_from_sessions([])
        assert result.value == 0.0

    def test_measure_creates_sample_data(self) -> None:
        """Full measure() creates temp data and returns a result."""
        measurer = ProjectDetectionMeasurer()
        result = measurer.measure()
        assert 0.0 <= result.value <= 100.0
        assert "total_sessions" in result.details

    def test_details_keys(self) -> None:
        sessions = [_make_session("proj")]
        result = ProjectDetectionMeasurer().measure_from_sessions(sessions)
        assert "total_sessions" in result.details
        assert "with_project" in result.details
        assert "without_project" in result.details
