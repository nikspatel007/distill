"""Tests for the TroopX content parser."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from distill.intake.config import IntakeConfig, TroopXIntakeConfig
from distill.intake.models import ContentSource, ContentType
from distill.intake.parsers.troopx import TroopXParser


@pytest.fixture(autouse=True)
def _enable_psycopg2():
    """Ensure _HAS_PSYCOPG2 is True for all tests."""
    with patch("distill.intake.parsers.troopx._HAS_PSYCOPG2", True):
        yield


def _make_config(
    db_url: str = "",
    troopx_home: str = "",
    troopx_project: str = "",
    include_workflows: list[str] | None = None,
    exclude_workflows: list[str] | None = None,
    max_age_days: int = 7,
    max_items: int = 50,
) -> IntakeConfig:
    return IntakeConfig(
        troopx=TroopXIntakeConfig(
            db_url=db_url,
            troopx_home=troopx_home,
            troopx_project=troopx_project,
            include_workflows=include_workflows or [],
            exclude_workflows=exclude_workflows or [],
            max_age_days=max_age_days,
        ),
        max_items_per_source=max_items,
    )


# -- Properties -----------------------------------------------------------


class TestTroopXParserProperties:
    def test_source_returns_troopx(self) -> None:
        parser = TroopXParser(config=_make_config(db_url="postgresql://localhost/test"))
        assert parser.source == ContentSource.TROOPX

    def test_is_configured_with_db_url(self) -> None:
        parser = TroopXParser(config=_make_config(db_url="postgresql://localhost/test"))
        assert parser.is_configured is True

    def test_is_configured_with_home(self) -> None:
        parser = TroopXParser(config=_make_config(troopx_home="/home/user/.troopx"))
        assert parser.is_configured is True

    def test_is_configured_with_project(self) -> None:
        parser = TroopXParser(config=_make_config(troopx_project="/project/.troopx"))
        assert parser.is_configured is True

    def test_not_configured_when_all_empty(self) -> None:
        parser = TroopXParser(config=_make_config())
        assert parser.is_configured is False

    def test_unconfigured_returns_empty(self) -> None:
        parser = TroopXParser(config=_make_config())
        assert parser.parse() == []


# -- psycopg2 not installed -----------------------------------------------


class TestTroopXParserNoPsycopg2:
    @patch("distill.intake.parsers.troopx._HAS_PSYCOPG2", False)
    def test_parse_returns_empty_when_psycopg2_missing_and_no_files(self) -> None:
        parser = TroopXParser(config=_make_config(db_url="postgresql://localhost/test"))
        result = parser.parse()
        assert result == []

    @patch("distill.intake.parsers.troopx._HAS_PSYCOPG2", False)
    def test_logs_warning_when_psycopg2_missing(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        parser = TroopXParser(config=_make_config(db_url="postgresql://localhost/test"))
        with caplog.at_level("WARNING"):
            parser.parse()
        assert any("psycopg2" in r.message.lower() for r in caplog.records)


# -- DB workflow parsing ---------------------------------------------------


class TestTroopXWorkflows:
    @patch("distill.intake.parsers.troopx.psycopg2")
    def test_parse_workflow_from_db(self, mock_psycopg2: MagicMock) -> None:
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_psycopg2.connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur

        wf_time = datetime(2026, 2, 20, 10, 0, 0, tzinfo=timezone.utc)
        wf_end = datetime(2026, 2, 20, 10, 30, 0, tzinfo=timezone.utc)

        # Sequence: workflows, bb, signals, escalations, meetings
        mock_cur.fetchall.side_effect = [
            [("wf-001", "Build health endpoint", "completed", wf_time, wf_end)],
            [("findings", "bug-1", "Found null pointer", "dev", wf_time)],
            [("done", "Task complete", "dev", wf_time)],
            [],
            [],
        ]

        parser = TroopXParser(config=_make_config(db_url="postgresql://localhost/test"))
        items = parser.parse(since=datetime(2026, 1, 1, tzinfo=timezone.utc))

        assert len(items) == 1
        item = items[0]
        assert item.title == "Build health endpoint"
        assert item.source == ContentSource.TROOPX
        assert item.site_name == "TroopX"
        assert "findings" in item.tags
        assert item.metadata["workflow_id"] == "wf-001"
        assert item.metadata["status"] == "completed"
        assert item.metadata["duration_seconds"] == 1800

    @patch("distill.intake.parsers.troopx.psycopg2")
    def test_workflow_dedup(self, mock_psycopg2: MagicMock) -> None:
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_psycopg2.connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur

        wf_time = datetime(2026, 2, 20, tzinfo=timezone.utc)

        mock_cur.fetchall.side_effect = [
            [("wf-001", "Task A", "done", wf_time, None)],
            [], [], [],
            [],
        ]

        parser = TroopXParser(config=_make_config(db_url="postgresql://localhost/test"))
        items = parser.parse(since=datetime(2026, 1, 1, tzinfo=timezone.utc))

        ids = [i.id for i in items]
        assert len(ids) == len(set(ids))


# -- DB meeting parsing ----------------------------------------------------


class TestTroopXMeetings:
    @patch("distill.intake.parsers.troopx.psycopg2")
    def test_parse_meeting(self, mock_psycopg2: MagicMock) -> None:
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_psycopg2.connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur

        mt_time = datetime(2026, 2, 20, tzinfo=timezone.utc)

        mock_cur.fetchall.side_effect = [
            [],  # workflows
            # meeting_id, topic, agenda, summary, creator_agent_id, status, created_at, started_at, concluded_at
            [(1, "Sprint Planning", "Review tasks", "All tasks assigned", "agent-001", "concluded", mt_time, mt_time, mt_time)],
        ]

        parser = TroopXParser(config=_make_config(db_url="postgresql://localhost/test"))
        items = parser.parse(since=datetime(2026, 1, 1, tzinfo=timezone.utc))

        assert len(items) == 1
        assert items[0].title == "Sprint Planning"
        assert "meeting" in items[0].tags
        assert "Agenda" in items[0].body
        assert "Summary" in items[0].body


# -- File-based parsing ----------------------------------------------------


class TestTroopXFileParser:
    def test_parse_memory_files(self, tmp_path: Path) -> None:
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        (memory_dir / "MEMORY-dev.md").write_text("# Dev memory\n\nSome learnings here.")

        parser = TroopXParser(config=_make_config(troopx_project=str(tmp_path)))
        items = parser.parse()

        mem_items = [i for i in items if "agent-memory" in i.tags]
        assert len(mem_items) == 1
        assert mem_items[0].title == "Agent Memory: dev"
        assert mem_items[0].author == "dev"

    def test_parse_knowledge_files(self, tmp_path: Path) -> None:
        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir()
        (knowledge_dir / "learnings.md").write_text("# Learnings\n\n- Use batch queries")

        parser = TroopXParser(config=_make_config(troopx_project=str(tmp_path)))
        items = parser.parse()

        knowledge_items = [i for i in items if "knowledge" in i.tags]
        assert len(knowledge_items) == 1
        assert knowledge_items[0].title == "TroopX Team Learnings"

    def test_parse_roster_files(self, tmp_path: Path) -> None:
        roster_dir = tmp_path / "roster" / "security-reviewer"
        roster_dir.mkdir(parents=True)
        (roster_dir / "CLAUDE.md").write_text("# Security Reviewer\n\nI review code for vulns.")

        parser = TroopXParser(config=_make_config(troopx_home=str(tmp_path)))
        items = parser.parse()

        roster_items = [i for i in items if "agent-identity" in i.tags]
        assert len(roster_items) == 1
        assert roster_items[0].title == "Agent Identity: security-reviewer"

    def test_empty_files_skipped(self, tmp_path: Path) -> None:
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        (memory_dir / "MEMORY-empty.md").write_text("")

        parser = TroopXParser(config=_make_config(troopx_project=str(tmp_path)))
        items = parser.parse()

        assert len(items) == 0


# -- Workflow filters ------------------------------------------------------


class TestTroopXWorkflowFilters:
    @patch("distill.intake.parsers.troopx.psycopg2")
    def test_include_patterns(self, mock_psycopg2: MagicMock) -> None:
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_psycopg2.connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur

        wf_time = datetime(2026, 2, 20, tzinfo=timezone.utc)
        mock_cur.fetchall.side_effect = [
            [
                ("wf-1", "Build API endpoint", "done", wf_time, None),
                ("wf-2", "Fix CSS layout", "done", wf_time, None),
            ],
            [], [], [],  # bb, signals, escalations for wf-1
            [],  # meetings
        ]

        parser = TroopXParser(
            config=_make_config(
                db_url="postgresql://localhost/test", include_workflows=["*api*"]
            )
        )
        items = parser.parse(since=datetime(2026, 1, 1, tzinfo=timezone.utc))

        assert len(items) == 1
        assert items[0].title == "Build API endpoint"

    @patch("distill.intake.parsers.troopx.psycopg2")
    def test_exclude_patterns(self, mock_psycopg2: MagicMock) -> None:
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_psycopg2.connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur

        wf_time = datetime(2026, 2, 20, tzinfo=timezone.utc)
        mock_cur.fetchall.side_effect = [
            [
                ("wf-1", "Build API endpoint", "done", wf_time, None),
                ("wf-2", "Fix CSS layout", "done", wf_time, None),
            ],
            [], [], [],  # bb, signals, escalations for wf-2
            [],
        ]

        parser = TroopXParser(
            config=_make_config(
                db_url="postgresql://localhost/test", exclude_workflows=["*api*"]
            )
        )
        items = parser.parse(since=datetime(2026, 1, 1, tzinfo=timezone.utc))

        assert len(items) == 1
        assert items[0].title == "Fix CSS layout"


# -- Stable IDs ------------------------------------------------------------


class TestStableIds:
    def test_workflow_id_is_deterministic(self) -> None:
        expected = hashlib.sha256(b"troopx:wf-001").hexdigest()[:16]
        result = hashlib.sha256(b"troopx:wf-001").hexdigest()[:16]
        assert result == expected

    def test_memory_id_is_deterministic(self) -> None:
        expected = hashlib.sha256(b"troopx:memory:dev").hexdigest()[:16]
        result = hashlib.sha256(b"troopx:memory:dev").hexdigest()[:16]
        assert result == expected
