"""Tests for content richness scoring and field coverage in core module."""

from datetime import datetime

import pytest

from distill.core import (
    analyze,
    compute_field_coverage,
    compute_richness_score,
)
from distill.parsers.models import (
    BaseSession,
    Message,
    SessionOutcome,
    ToolCall,
    ToolUsageSummary,
)


class TestComputeRichnessScore:
    """Tests for compute_richness_score."""

    def test_empty_session_scores_zero(self) -> None:
        """A session with no populated fields should score 0."""
        session = BaseSession(
            session_id="empty",
            timestamp=datetime(2024, 1, 1),
        )
        score = compute_richness_score(session)
        assert score == 0.0

    def test_fully_populated_session_scores_one(self) -> None:
        """A session with all richness fields populated should score 1.0."""
        session = BaseSession(
            session_id="full",
            timestamp=datetime(2024, 1, 1, 10, 0),
            end_time=datetime(2024, 1, 1, 11, 0),
            summary="A detailed summary",
            messages=[Message(role="user", content="hello")],
            tool_calls=[ToolCall(tool_name="Read")],
            outcomes=[SessionOutcome(description="Completed task")],
            tags=["coding", "debug"],
        )
        score = compute_richness_score(session)
        assert score == 1.0

    def test_partial_session_scores_fraction(self) -> None:
        """A session with some fields populated should score between 0 and 1."""
        session = BaseSession(
            session_id="partial",
            timestamp=datetime(2024, 1, 1),
            summary="Has summary",
            messages=[Message(role="user", content="hello")],
        )
        score = compute_richness_score(session)
        assert 0.0 < score < 1.0

    def test_score_is_between_zero_and_one(self) -> None:
        """Score should always be in [0.0, 1.0]."""
        session = BaseSession(
            session_id="any",
            timestamp=datetime(2024, 1, 1),
            summary="test",
        )
        score = compute_richness_score(session)
        assert 0.0 <= score <= 1.0

    def test_tools_used_derived_from_tool_calls(self) -> None:
        """tools_used auto-derived from tool_calls should count for richness."""
        session = BaseSession(
            session_id="tools",
            timestamp=datetime(2024, 1, 1),
            tool_calls=[ToolCall(tool_name="Read"), ToolCall(tool_name="Write")],
        )
        # tools_used is auto-derived in model_post_init
        assert len(session.tools_used) > 0
        score = compute_richness_score(session)
        # Should get credit for tools_used
        assert score > 0.0


class TestComputeFieldCoverage:
    """Tests for compute_field_coverage."""

    def test_empty_sessions_all_zero(self) -> None:
        """Coverage should be 0 for all fields with no sessions."""
        coverage = compute_field_coverage([])
        assert all(v == 0.0 for v in coverage.values())

    def test_single_full_session_all_one(self) -> None:
        """Coverage should be 1.0 for all fields when every field is populated."""
        session = BaseSession(
            session_id="full",
            timestamp=datetime(2024, 1, 1, 10, 0),
            end_time=datetime(2024, 1, 1, 11, 0),
            summary="Summary",
            messages=[Message(role="user", content="hi")],
            tool_calls=[ToolCall(tool_name="Read")],
            outcomes=[SessionOutcome(description="Done")],
            tags=["tag1"],
        )
        coverage = compute_field_coverage([session])
        assert all(v == 1.0 for v in coverage.values())

    def test_half_coverage(self) -> None:
        """Two sessions, one full and one empty, should give ~0.5 coverage."""
        full_session = BaseSession(
            session_id="full",
            timestamp=datetime(2024, 1, 1, 10, 0),
            end_time=datetime(2024, 1, 1, 11, 0),
            summary="Summary",
            messages=[Message(role="user", content="hi")],
            tool_calls=[ToolCall(tool_name="Read")],
            outcomes=[SessionOutcome(description="Done")],
            tags=["tag1"],
        )
        empty_session = BaseSession(
            session_id="empty",
            timestamp=datetime(2024, 1, 1),
        )
        coverage = compute_field_coverage([full_session, empty_session])
        # Each field should be 0.5 (1 out of 2 sessions)
        for field, value in coverage.items():
            assert value == 0.5, f"Field {field} expected 0.5, got {value}"

    def test_coverage_returns_all_richness_fields(self) -> None:
        """Coverage dict should contain all tracked fields."""
        from distill.core import _RICHNESS_FIELDS

        session = BaseSession(
            session_id="test",
            timestamp=datetime(2024, 1, 1),
        )
        coverage = compute_field_coverage([session])
        for field in _RICHNESS_FIELDS:
            assert field in coverage, f"Missing field: {field}"


class TestAnalyzeIncludesRichnessAndCoverage:
    """Tests that analyze() populates richness and coverage in stats."""

    def test_analyze_populates_richness_score(self) -> None:
        """analyze() should compute a content_richness_score in stats."""
        session = BaseSession(
            session_id="test",
            timestamp=datetime(2024, 1, 1, 10, 0),
            summary="A session",
            messages=[Message(role="user", content="hi")],
        )
        result = analyze([session])
        assert result.stats.content_richness_score >= 0.0
        assert result.stats.content_richness_score <= 1.0

    def test_analyze_populates_field_coverage(self) -> None:
        """analyze() should compute field_coverage in stats."""
        session = BaseSession(
            session_id="test",
            timestamp=datetime(2024, 1, 1, 10, 0),
            summary="A session",
        )
        result = analyze([session])
        assert isinstance(result.stats.field_coverage, dict)
        assert len(result.stats.field_coverage) > 0

    def test_analyze_empty_sessions_zero_richness(self) -> None:
        """analyze() with empty list should give 0 richness."""
        result = analyze([])
        assert result.stats.content_richness_score == 0.0
        assert result.stats.field_coverage == {}
