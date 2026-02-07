"""Tests for project derivation and narrative enrichment in parsers."""

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from distill.parsers.claude import ClaudeParser
from distill.parsers.codex import CodexParser


def _write_claude_session(tmpdir: Path, session_id: str, cwd: str) -> Path:
    """Write a minimal Claude session JSONL file."""
    projects_dir = tmpdir / ".claude" / "projects" / "test-proj"
    projects_dir.mkdir(parents=True, exist_ok=True)
    session_file = projects_dir / f"{session_id}.jsonl"
    ts = "2024-06-15T10:00:00Z"
    lines = [
        json.dumps(
            {
                "type": "user",
                "timestamp": ts,
                "cwd": cwd,
                "sessionId": session_id,
                "message": {"content": "Help me fix a bug"},
            }
        ),
        json.dumps(
            {
                "type": "assistant",
                "timestamp": "2024-06-15T10:01:00Z",
                "message": {"content": "Sure, let me look at the code."},
            }
        ),
    ]
    session_file.write_text("\n".join(lines), encoding="utf-8")
    return tmpdir / ".claude"


def _write_codex_session(tmpdir: Path, session_id: str, cwd: str) -> Path:
    """Write a minimal Codex session JSONL file."""
    sessions_dir = tmpdir / ".codex" / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    session_file = sessions_dir / f"rollout-{session_id}.jsonl"
    lines = [
        json.dumps(
            {
                "session_id": session_id,
                "cwd": cwd,
                "model": "codex",
                "timestamp": "2024-06-15T10:00:00Z",
            }
        ),
        json.dumps(
            {
                "type": "user",
                "timestamp": "2024-06-15T10:00:00Z",
                "message": {"content": "Implement feature X"},
            }
        ),
        json.dumps(
            {
                "type": "assistant",
                "timestamp": "2024-06-15T10:01:00Z",
                "message": {"content": "Working on it."},
            }
        ),
    ]
    session_file.write_text("\n".join(lines), encoding="utf-8")
    return tmpdir / ".codex"


class TestClaudeProjectDerivation:
    """Test that ClaudeParser derives project from cwd."""

    def test_project_from_cwd(self, tmp_path: Path) -> None:
        claude_dir = _write_claude_session(
            tmp_path, "sess1", "/home/user/projects/my-app"
        )
        parser = ClaudeParser()
        sessions = parser.parse_directory(claude_dir)
        assert len(sessions) == 1
        assert sessions[0].project == "my-app"

    def test_project_empty_when_no_cwd(self, tmp_path: Path) -> None:
        claude_dir = _write_claude_session(tmp_path, "sess2", "")
        parser = ClaudeParser()
        sessions = parser.parse_directory(claude_dir)
        assert len(sessions) == 1
        assert sessions[0].project == ""

    def test_narrative_populated(self, tmp_path: Path) -> None:
        claude_dir = _write_claude_session(
            tmp_path, "sess3", "/home/user/projects/test-proj"
        )
        parser = ClaudeParser()
        sessions = parser.parse_directory(claude_dir)
        assert len(sessions) == 1
        assert sessions[0].narrative != ""
        # Narrative should reference the summary
        assert "Help me fix a bug" in sessions[0].narrative


class TestCodexProjectDerivation:
    """Test that CodexParser derives project from cwd."""

    def test_project_from_cwd(self, tmp_path: Path) -> None:
        codex_dir = _write_codex_session(
            tmp_path, "sess1", "/home/user/projects/backend-api"
        )
        parser = CodexParser()
        sessions = parser.parse_directory(codex_dir)
        assert len(sessions) == 1
        assert sessions[0].project == "backend-api"

    def test_narrative_populated(self, tmp_path: Path) -> None:
        codex_dir = _write_codex_session(
            tmp_path, "sess2", "/home/user/projects/web-ui"
        )
        parser = CodexParser()
        sessions = parser.parse_directory(codex_dir)
        assert len(sessions) == 1
        assert sessions[0].narrative != ""
