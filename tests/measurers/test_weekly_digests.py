"""Tests for weekly_digests KPI measurer."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from distill.measurers.base import KPIResult
from distill.measurers.weekly_digests import (
    WEEKLY_DIGEST_MARKERS,
    WeeklyDigestsMeasurer,
    _create_multi_week_data,
    _generate_weekly_digests_to_disk,
)


class TestWeeklyDigestsMeasurer:
    def test_kpi_name(self) -> None:
        assert WeeklyDigestsMeasurer.KPI_NAME == "weekly_digests"

    def test_target_is_100(self) -> None:
        assert WeeklyDigestsMeasurer.TARGET == 100.0

    def test_measure_returns_result(self) -> None:
        measurer = WeeklyDigestsMeasurer()
        result = measurer.measure()
        assert isinstance(result, KPIResult)
        assert 0.0 <= result.value <= 100.0

    def test_measure_has_expected_details(self) -> None:
        result = WeeklyDigestsMeasurer().measure()
        assert "expected_weeks" in result.details
        assert "generated_digests" in result.details
        assert "valid_digests" in result.details

    def test_measure_from_output_missing_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = WeeklyDigestsMeasurer().measure_from_output(Path(tmpdir))
            assert result.value == 0.0
            assert "not found" in result.details["error"]

    def test_measure_from_output_empty_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            weekly_dir = Path(tmpdir) / "weekly"
            weekly_dir.mkdir()
            result = WeeklyDigestsMeasurer().measure_from_output(Path(tmpdir))
            assert result.value == 0.0
            assert "no weekly digest" in result.details["error"]

    def test_measure_from_output_valid_digest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            weekly_dir = Path(tmpdir) / "weekly"
            weekly_dir.mkdir()
            content = (
                "# Weekly Digest: 2024-W24\n\n"
                "## Overview\n\nA productive week.\n\n"
                "## Daily Breakdown\n\nMonday: worked on things.\n"
            )
            (weekly_dir / "weekly-2024-W24.md").write_text(content)
            result = WeeklyDigestsMeasurer().measure_from_output(Path(tmpdir))
            assert result.value == 100.0

    def test_measure_from_output_invalid_digest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            weekly_dir = Path(tmpdir) / "weekly"
            weekly_dir.mkdir()
            (weekly_dir / "weekly-2024-W24.md").write_text("just some text\n")
            result = WeeklyDigestsMeasurer().measure_from_output(Path(tmpdir))
            assert result.value == 0.0


class TestCreateMultiWeekData:
    def test_creates_session_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            _create_multi_week_data(base)
            project_dir = base / ".claude" / "projects" / "test-project"
            assert project_dir.exists()
            session_files = list(project_dir.glob("sess-wk-*.jsonl"))
            assert len(session_files) == 3


class TestGenerateWeeklyDigests:
    def test_generates_files(self) -> None:
        """Full pipeline: create data, parse, generate digests."""
        from distill.core import discover_sessions, parse_session_file

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            _create_multi_week_data(base)

            all_sessions = []
            discovered = discover_sessions(base, sources=None)
            for src, paths in discovered.items():
                for path in paths:
                    all_sessions.extend(parse_session_file(path, src))

            output_dir = base / "output"
            files = _generate_weekly_digests_to_disk(all_sessions, output_dir)
            assert len(files) >= 1
            for f in files:
                assert f.exists()
                content = f.read_text()
                assert "# Weekly Digest:" in content


class TestDigestMarkers:
    def test_markers_defined(self) -> None:
        assert len(WEEKLY_DIGEST_MARKERS) >= 3
        names = [name for name, _ in WEEKLY_DIGEST_MARKERS]
        assert "has_title" in names
        assert "has_overview" in names
        assert "has_daily_breakdown" in names
