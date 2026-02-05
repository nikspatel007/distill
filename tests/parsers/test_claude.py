"""Tests for Claude session parser."""

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from session_insights.parsers.claude import ClaudeParser, ClaudeSession
from session_insights.parsers.models import BaseSession, Message, ToolUsage


class TestModels:
    """Tests for parser models."""

    def test_message_creation(self) -> None:
        """Test creating a Message object."""
        msg = Message(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.timestamp is None

    def test_message_with_timestamp(self) -> None:
        """Test creating a Message with timestamp."""
        ts = datetime(2024, 1, 1, 12, 0, 0)
        msg = Message(role="assistant", content="Hi there", timestamp=ts)
        assert msg.timestamp == ts

    def test_tool_usage_creation(self) -> None:
        """Test creating a ToolUsage object."""
        tool = ToolUsage(tool_name="Read", arguments={"path": "/test"})
        assert tool.tool_name == "Read"
        assert tool.arguments == {"path": "/test"}
        assert tool.result is None
        assert tool.duration_ms is None

    def test_tool_usage_with_result(self) -> None:
        """Test ToolUsage with result and duration."""
        tool = ToolUsage(
            tool_name="Bash",
            arguments={"command": "ls"},
            result="file1.txt\nfile2.txt",
            duration_ms=150,
        )
        assert tool.result == "file1.txt\nfile2.txt"
        assert tool.duration_ms == 150

    def test_base_session_creation(self) -> None:
        """Test creating a BaseSession object."""
        session = BaseSession(
            session_id="test-123",
            timestamp=datetime.now(),
        )
        assert session.session_id == "test-123"
        assert session.source == "unknown"
        assert session.messages == []
        assert session.tool_calls == []

    def test_base_session_duration_no_messages(self) -> None:
        """Test duration calculation with no messages."""
        session = BaseSession(
            session_id="test-123",
            timestamp=datetime.now(),
        )
        assert session.duration_minutes is None

    def test_base_session_duration_single_message(self) -> None:
        """Test duration calculation with single message."""
        session = BaseSession(
            session_id="test-123",
            timestamp=datetime.now(),
            messages=[Message(role="user", content="Hi", timestamp=datetime.now())],
        )
        assert session.duration_minutes is None

    def test_base_session_duration_multiple_messages(self) -> None:
        """Test duration calculation with multiple messages."""
        t1 = datetime(2024, 1, 1, 12, 0, 0)
        t2 = datetime(2024, 1, 1, 12, 30, 0)  # 30 minutes later
        session = BaseSession(
            session_id="test-123",
            timestamp=t1,
            messages=[
                Message(role="user", content="Hi", timestamp=t1),
                Message(role="assistant", content="Hello", timestamp=t2),
            ],
        )
        assert session.duration_minutes == 30.0


class TestClaudeSession:
    """Tests for ClaudeSession model."""

    def test_claude_session_source(self) -> None:
        """Test that ClaudeSession has correct source."""
        session = ClaudeSession(
            session_id="test-123",
            timestamp=datetime.now(),
        )
        assert session.source == "claude-code"

    def test_claude_session_extra_fields(self) -> None:
        """Test ClaudeSession extra fields."""
        session = ClaudeSession(
            session_id="test-123",
            timestamp=datetime.now(),
            model="claude-3-sonnet",
            git_branch="main",
            cwd="/home/user/project",
            version="1.0.0",
        )
        assert session.model == "claude-3-sonnet"
        assert session.git_branch == "main"
        assert session.cwd == "/home/user/project"
        assert session.version == "1.0.0"

    def test_note_name_generation(self) -> None:
        """Test Obsidian note name generation."""
        ts = datetime(2024, 3, 15, 14, 30, 0)
        session = ClaudeSession(
            session_id="abc12345-def6-7890",
            timestamp=ts,
        )
        assert session.note_name == "session-2024-03-15-1430-abc12345"


class TestClaudeParser:
    """Tests for ClaudeParser."""

    @pytest.fixture
    def parser(self) -> ClaudeParser:
        """Create a parser instance."""
        return ClaudeParser()

    @pytest.fixture
    def temp_dir(self) -> Path:
        """Create a temporary directory for test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_parser_initialization(self, parser: ClaudeParser) -> None:
        """Test parser initialization."""
        assert parser.parse_errors == []

    def test_parse_empty_directory(self, parser: ClaudeParser, temp_dir: Path) -> None:
        """Test parsing an empty directory."""
        sessions = parser.parse_directory(temp_dir)
        assert sessions == []

    def test_parse_simple_session(self, parser: ClaudeParser, temp_dir: Path) -> None:
        """Test parsing a simple session file."""
        session_file = temp_dir / "test-session.jsonl"
        entries = [
            {
                "type": "user",
                "timestamp": "2024-01-15T10:30:00Z",
                "message": {"content": "Hello Claude"},
            },
            {
                "type": "assistant",
                "timestamp": "2024-01-15T10:30:05Z",
                "message": {
                    "content": [{"type": "text", "text": "Hello! How can I help you?"}],
                    "model": "claude-3-sonnet",
                },
            },
        ]
        session_file.write_text("\n".join(json.dumps(e) for e in entries))

        sessions = parser.parse_directory(temp_dir)
        assert len(sessions) == 1
        session = sessions[0]
        assert session.session_id == "test-session"
        assert len(session.messages) == 2
        assert session.messages[0].role == "user"
        assert session.messages[0].content == "Hello Claude"
        assert session.messages[1].role == "assistant"

    def test_parse_session_with_tool_calls(
        self, parser: ClaudeParser, temp_dir: Path
    ) -> None:
        """Test parsing a session with tool calls."""
        session_file = temp_dir / "tool-session.jsonl"
        entries = [
            {
                "type": "user",
                "timestamp": "2024-01-15T10:30:00Z",
                "message": {"content": "List files in current directory"},
            },
            {
                "type": "assistant",
                "timestamp": "2024-01-15T10:30:05Z",
                "message": {
                    "content": [
                        {"type": "text", "text": "I'll list the files for you."},
                        {
                            "type": "tool_use",
                            "id": "tool-123",
                            "name": "Bash",
                            "input": {"command": "ls -la"},
                        },
                    ],
                },
            },
            {
                "type": "user",
                "timestamp": "2024-01-15T10:30:10Z",
                "toolUseResult": {"durationMs": 50},
                "message": {
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "tool-123",
                            "content": "file1.txt\nfile2.txt",
                        }
                    ]
                },
            },
        ]
        session_file.write_text("\n".join(json.dumps(e) for e in entries))

        sessions = parser.parse_directory(temp_dir)
        assert len(sessions) == 1
        session = sessions[0]
        assert len(session.tool_calls) == 1
        tool_call = session.tool_calls[0]
        assert tool_call.tool_name == "Bash"
        assert tool_call.arguments == {"command": "ls -la"}
        assert tool_call.result == "file1.txt\nfile2.txt"
        assert tool_call.duration_ms == 50

    def test_parse_session_with_metadata(
        self, parser: ClaudeParser, temp_dir: Path
    ) -> None:
        """Test parsing a session with git and environment metadata."""
        session_file = temp_dir / "meta-session.jsonl"
        entries = [
            {
                "type": "user",
                "timestamp": "2024-01-15T10:30:00Z",
                "sessionId": "custom-session-id",
                "gitBranch": "feature/test",
                "cwd": "/home/user/myproject",
                "version": "0.5.0",
                "message": {"content": "Hello"},
            },
        ]
        session_file.write_text("\n".join(json.dumps(e) for e in entries))

        sessions = parser.parse_directory(temp_dir)
        assert len(sessions) == 1
        session = sessions[0]
        assert session.session_id == "custom-session-id"
        assert session.git_branch == "feature/test"
        assert session.cwd == "/home/user/myproject"
        assert session.version == "0.5.0"

    def test_parse_claude_directory_structure(
        self, parser: ClaudeParser, temp_dir: Path
    ) -> None:
        """Test parsing the standard .claude directory structure."""
        # Create .claude/projects/project-name/ structure
        claude_dir = temp_dir / ".claude"
        projects_dir = claude_dir / "projects"
        project_dir = projects_dir / "test-project"
        project_dir.mkdir(parents=True)

        session_file = project_dir / "session-1.jsonl"
        entries = [
            {
                "type": "user",
                "timestamp": "2024-01-15T10:30:00Z",
                "message": {"content": "Hello"},
            },
        ]
        session_file.write_text("\n".join(json.dumps(e) for e in entries))

        sessions = parser.parse_directory(claude_dir)
        assert len(sessions) == 1

    def test_parse_multiple_projects(
        self, parser: ClaudeParser, temp_dir: Path
    ) -> None:
        """Test parsing multiple projects in .claude directory."""
        projects_dir = temp_dir / "projects"

        for project_name in ["project-a", "project-b"]:
            project_dir = projects_dir / project_name
            project_dir.mkdir(parents=True)
            session_file = project_dir / "session.jsonl"
            entries = [
                {
                    "type": "user",
                    "timestamp": "2024-01-15T10:30:00Z",
                    "message": {"content": f"Hello from {project_name}"},
                },
            ]
            session_file.write_text("\n".join(json.dumps(e) for e in entries))

        sessions = parser.parse_directory(temp_dir)
        assert len(sessions) == 2

    def test_parse_sessions_subdirectory(
        self, parser: ClaudeParser, temp_dir: Path
    ) -> None:
        """Test parsing sessions from sessions/ subdirectory."""
        sessions_dir = temp_dir / "sessions"
        sessions_dir.mkdir()

        session_file = sessions_dir / "session-abc.jsonl"
        entries = [
            {
                "type": "user",
                "timestamp": "2024-01-15T10:30:00Z",
                "message": {"content": "Hello from sessions subdir"},
            },
        ]
        session_file.write_text("\n".join(json.dumps(e) for e in entries))

        sessions = parser.parse_directory(temp_dir)
        assert len(sessions) == 1
        assert sessions[0].messages[0].content == "Hello from sessions subdir"

    def test_parse_json_extension(
        self, parser: ClaudeParser, temp_dir: Path
    ) -> None:
        """Test parsing .json files (not just .jsonl)."""
        session_file = temp_dir / "session.json"
        entries = [
            {
                "type": "user",
                "timestamp": "2024-01-15T10:30:00Z",
                "message": {"content": "JSON extension test"},
            },
        ]
        session_file.write_text("\n".join(json.dumps(e) for e in entries))

        sessions = parser.parse_directory(temp_dir)
        assert len(sessions) == 1

    def test_parse_full_claude_sessions_structure(
        self, parser: ClaudeParser, temp_dir: Path
    ) -> None:
        """Test parsing the full .claude/projects/*/sessions/*.json structure."""
        # Create .claude/projects/project-name/sessions/ structure
        claude_dir = temp_dir / ".claude"
        projects_dir = claude_dir / "projects"
        project_dir = projects_dir / "my-project"
        sessions_dir = project_dir / "sessions"
        sessions_dir.mkdir(parents=True)

        # Add sessions in the sessions/ subdirectory
        for i, session_name in enumerate(["abc123", "def456"]):
            session_file = sessions_dir / f"{session_name}.json"
            entries = [
                {
                    "type": "user",
                    "timestamp": f"2024-01-15T10:3{i}:00Z",
                    "message": {"content": f"Session {session_name}"},
                },
            ]
            session_file.write_text("\n".join(json.dumps(e) for e in entries))

        sessions = parser.parse_directory(claude_dir)
        assert len(sessions) == 2

    def test_parse_mixed_locations(
        self, parser: ClaudeParser, temp_dir: Path
    ) -> None:
        """Test parsing sessions from both project root and sessions/ subdir."""
        # Session directly in project dir
        direct_session = temp_dir / "direct.jsonl"
        entries = [
            {
                "type": "user",
                "timestamp": "2024-01-15T10:30:00Z",
                "message": {"content": "Direct session"},
            },
        ]
        direct_session.write_text("\n".join(json.dumps(e) for e in entries))

        # Session in sessions/ subdir
        sessions_dir = temp_dir / "sessions"
        sessions_dir.mkdir()
        subdir_session = sessions_dir / "subdir.json"
        entries2 = [
            {
                "type": "user",
                "timestamp": "2024-01-15T10:35:00Z",
                "message": {"content": "Subdir session"},
            },
        ]
        subdir_session.write_text("\n".join(json.dumps(e) for e in entries2))

        sessions = parser.parse_directory(temp_dir)
        assert len(sessions) == 2

    def test_handle_malformed_json(
        self, parser: ClaudeParser, temp_dir: Path
    ) -> None:
        """Test graceful handling of malformed JSON lines."""
        session_file = temp_dir / "bad-session.jsonl"
        content = """{\"type\": \"user\", \"message\": {\"content\": \"Valid\"}, \"timestamp\": \"2024-01-15T10:30:00Z\"}
{invalid json line}
{\"type\": \"assistant\", \"message\": {\"content\": [{\"type\": \"text\", \"text\": \"Also valid\"}]}, \"timestamp\": \"2024-01-15T10:30:05Z\"}"""
        session_file.write_text(content)

        sessions = parser.parse_directory(temp_dir)
        assert len(sessions) == 1
        assert len(sessions[0].messages) == 2  # Both valid messages parsed
        assert len(parser.parse_errors) > 0  # Error recorded for malformed line

    def test_handle_empty_session_file(
        self, parser: ClaudeParser, temp_dir: Path
    ) -> None:
        """Test handling of empty session files."""
        session_file = temp_dir / "empty.jsonl"
        session_file.write_text("")

        sessions = parser.parse_directory(temp_dir)
        assert sessions == []

    def test_handle_session_with_no_messages(
        self, parser: ClaudeParser, temp_dir: Path
    ) -> None:
        """Test handling of session file with no valid messages."""
        session_file = temp_dir / "no-messages.jsonl"
        entries = [
            {"type": "unknown", "data": "something"},
        ]
        session_file.write_text("\n".join(json.dumps(e) for e in entries))

        sessions = parser.parse_directory(temp_dir)
        assert sessions == []

    def test_handle_missing_timestamp(
        self, parser: ClaudeParser, temp_dir: Path
    ) -> None:
        """Test handling of entries with missing timestamps."""
        session_file = temp_dir / "no-timestamp.jsonl"
        entries = [
            {"type": "user", "message": {"content": "No timestamp here"}},
        ]
        session_file.write_text("\n".join(json.dumps(e) for e in entries))

        sessions = parser.parse_directory(temp_dir)
        assert len(sessions) == 1
        # Should use file modification time as fallback
        assert sessions[0].timestamp is not None

    def test_handle_missing_content(
        self, parser: ClaudeParser, temp_dir: Path
    ) -> None:
        """Test handling of entries with missing content."""
        session_file = temp_dir / "missing-content.jsonl"
        entries = [
            {"type": "user", "timestamp": "2024-01-15T10:30:00Z", "message": {}},
            {
                "type": "user",
                "timestamp": "2024-01-15T10:30:05Z",
                "message": {"content": "Valid message"},
            },
        ]
        session_file.write_text("\n".join(json.dumps(e) for e in entries))

        sessions = parser.parse_directory(temp_dir)
        assert len(sessions) == 1
        # Only the valid message should be parsed
        assert len(sessions[0].messages) == 1

    def test_parse_session_file_method(
        self, parser: ClaudeParser, temp_dir: Path
    ) -> None:
        """Test the public parse_session_file method."""
        session_file = temp_dir / "single-session.jsonl"
        entries = [
            {
                "type": "user",
                "timestamp": "2024-01-15T10:30:00Z",
                "message": {"content": "Test message"},
            },
        ]
        session_file.write_text("\n".join(json.dumps(e) for e in entries))

        session = parser.parse_session_file(session_file)
        assert session is not None
        assert session.session_id == "single-session"
        assert len(session.messages) == 1

    def test_parse_session_file_nonexistent(self, parser: ClaudeParser) -> None:
        """Test parsing a nonexistent file."""
        session = parser.parse_session_file(Path("/nonexistent/file.jsonl"))
        assert session is None
        assert len(parser.parse_errors) > 0

    def test_parse_session_with_text_array_content(
        self, parser: ClaudeParser, temp_dir: Path
    ) -> None:
        """Test parsing user messages with array content containing text items."""
        session_file = temp_dir / "array-content.jsonl"
        entries = [
            {
                "type": "user",
                "timestamp": "2024-01-15T10:30:00Z",
                "message": {
                    "content": [
                        {"type": "text", "text": "First part"},
                        {"type": "text", "text": "Second part"},
                    ]
                },
            },
        ]
        session_file.write_text("\n".join(json.dumps(e) for e in entries))

        sessions = parser.parse_directory(temp_dir)
        assert len(sessions) == 1
        assert len(sessions[0].messages) == 2

    def test_parse_errors_cleared_on_new_parse(
        self, parser: ClaudeParser, temp_dir: Path
    ) -> None:
        """Test that parse errors are cleared on each parse call."""
        # First parse with error
        bad_file = temp_dir / "bad.jsonl"
        bad_file.write_text("{invalid}")
        parser.parse_directory(temp_dir)
        assert len(parser.parse_errors) > 0

        # Second parse with good file
        bad_file.unlink()
        good_file = temp_dir / "good.jsonl"
        entries = [
            {
                "type": "user",
                "timestamp": "2024-01-15T10:30:00Z",
                "message": {"content": "Valid"},
            },
        ]
        good_file.write_text("\n".join(json.dumps(e) for e in entries))
        parser.parse_directory(temp_dir)
        assert len(parser.parse_errors) == 0

    def test_tool_use_without_result(
        self, parser: ClaudeParser, temp_dir: Path
    ) -> None:
        """Test that tool uses without results are still captured."""
        session_file = temp_dir / "pending-tool.jsonl"
        entries = [
            {
                "type": "user",
                "timestamp": "2024-01-15T10:29:55Z",
                "message": {"content": "Read this file"},
            },
            {
                "type": "assistant",
                "timestamp": "2024-01-15T10:30:00Z",
                "message": {
                    "content": [
                        {"type": "text", "text": "Reading the file..."},
                        {
                            "type": "tool_use",
                            "id": "tool-456",
                            "name": "Read",
                            "input": {"file_path": "/some/file"},
                        },
                    ],
                },
            },
        ]
        session_file.write_text("\n".join(json.dumps(e) for e in entries))

        sessions = parser.parse_directory(temp_dir)
        assert len(sessions) == 1
        assert len(sessions[0].tool_calls) == 1
        assert sessions[0].tool_calls[0].tool_name == "Read"
        assert sessions[0].tool_calls[0].result is None


class TestParserEdgeCases:
    """Edge case tests for parser robustness."""

    @pytest.fixture
    def parser(self) -> ClaudeParser:
        """Create a parser instance."""
        return ClaudeParser()

    @pytest.fixture
    def temp_dir(self) -> Path:
        """Create a temporary directory for test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_parse_unicode_content(
        self, parser: ClaudeParser, temp_dir: Path
    ) -> None:
        """Test parsing content with unicode characters."""
        session_file = temp_dir / "unicode.jsonl"
        entries = [
            {
                "type": "user",
                "timestamp": "2024-01-15T10:30:00Z",
                "message": {"content": "Hello 世界! 🚀 Привет мир!"},
            },
        ]
        session_file.write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in entries))

        sessions = parser.parse_directory(temp_dir)
        assert len(sessions) == 1
        assert "世界" in sessions[0].messages[0].content
        assert "🚀" in sessions[0].messages[0].content

    def test_parse_very_long_content(
        self, parser: ClaudeParser, temp_dir: Path
    ) -> None:
        """Test parsing very long message content."""
        session_file = temp_dir / "long-content.jsonl"
        long_text = "x" * 100000  # 100KB of content
        entries = [
            {
                "type": "user",
                "timestamp": "2024-01-15T10:30:00Z",
                "message": {"content": long_text},
            },
        ]
        session_file.write_text("\n".join(json.dumps(e) for e in entries))

        sessions = parser.parse_directory(temp_dir)
        assert len(sessions) == 1
        assert len(sessions[0].messages[0].content) == 100000

    def test_parse_blank_lines_in_jsonl(
        self, parser: ClaudeParser, temp_dir: Path
    ) -> None:
        """Test that blank lines in JSONL are handled gracefully."""
        session_file = temp_dir / "blanks.jsonl"
        content = """{\"type\": \"user\", \"message\": {\"content\": \"Hello\"}, \"timestamp\": \"2024-01-15T10:30:00Z\"}

{\"type\": \"assistant\", \"message\": {\"content\": [{\"type\": \"text\", \"text\": \"Hi\"}]}, \"timestamp\": \"2024-01-15T10:30:05Z\"}

"""
        session_file.write_text(content)

        sessions = parser.parse_directory(temp_dir)
        assert len(sessions) == 1
        assert len(sessions[0].messages) == 2

    def test_timestamp_timezone_handling(
        self, parser: ClaudeParser, temp_dir: Path
    ) -> None:
        """Test handling of different timestamp formats."""
        session_file = temp_dir / "timestamps.jsonl"
        entries = [
            {
                "type": "user",
                "timestamp": "2024-01-15T10:30:00Z",  # UTC with Z suffix
                "message": {"content": "UTC time"},
            },
            {
                "type": "user",
                "timestamp": "2024-01-15T10:30:00+00:00",  # UTC with offset
                "message": {"content": "UTC offset"},
            },
        ]
        session_file.write_text("\n".join(json.dumps(e) for e in entries))

        sessions = parser.parse_directory(temp_dir)
        assert len(sessions) == 1
        assert len(sessions[0].messages) == 2

    def test_nested_tool_input(
        self, parser: ClaudeParser, temp_dir: Path
    ) -> None:
        """Test parsing tool calls with nested input structures."""
        session_file = temp_dir / "nested-input.jsonl"
        entries = [
            {
                "type": "user",
                "timestamp": "2024-01-15T10:29:55Z",
                "message": {"content": "Edit the file"},
            },
            {
                "type": "assistant",
                "timestamp": "2024-01-15T10:30:00Z",
                "message": {
                    "content": [
                        {"type": "text", "text": "Editing the file..."},
                        {
                            "type": "tool_use",
                            "id": "tool-789",
                            "name": "Edit",
                            "input": {
                                "file_path": "/test.py",
                                "changes": [
                                    {"line": 1, "content": "import os"},
                                    {"line": 2, "content": "import sys"},
                                ],
                            },
                        },
                    ],
                },
            },
        ]
        session_file.write_text("\n".join(json.dumps(e) for e in entries))

        sessions = parser.parse_directory(temp_dir)
        assert len(sessions) == 1
        assert len(sessions[0].tool_calls) == 1
        assert "changes" in sessions[0].tool_calls[0].arguments
