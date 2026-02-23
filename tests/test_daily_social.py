"""Tests for the daily social post generation pipeline."""

import json
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from distill.pipeline.social import (
    DAILY_SOCIAL_STATE_FILENAME,
    STORY_SELECTOR_PROMPT,
    DailySocialState,
    _fetch_troopx_highlights,
    _load_daily_social_state,
    _save_daily_social_state,
    _select_story,
    generate_daily_social,
)
from distill.integrations.postiz import PostizConfig


def _make_subprocess_result(stdout="Post content"):
    """Create a mock subprocess.CompletedProcess."""
    result = MagicMock()
    result.returncode = 0
    result.stdout = stdout
    result.stderr = ""
    return result


class TestDailySocialState:
    def test_defaults(self):
        state = DailySocialState()
        assert state.day_number == 0
        assert state.last_posted_date == ""
        assert state.series_name == "100 days of building in public"

    def test_round_trip(self, tmp_path):
        state = DailySocialState(day_number=42, last_posted_date="2026-02-15")
        _save_daily_social_state(state, tmp_path)

        loaded = _load_daily_social_state(tmp_path)
        assert loaded.day_number == 42
        assert loaded.last_posted_date == "2026-02-15"

    def test_load_missing_file(self, tmp_path):
        state = _load_daily_social_state(tmp_path)
        assert state.day_number == 0

    def test_load_corrupt_file(self, tmp_path):
        state_path = tmp_path / "blog" / DAILY_SOCIAL_STATE_FILENAME
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text("not json", encoding="utf-8")
        state = _load_daily_social_state(tmp_path)
        assert state.day_number == 0


class TestGenerateDailySocial:
    """Tests for the generate_daily_social function."""

    def _make_config(self, **overrides):
        defaults = {
            "url": "https://postiz.test",
            "api_key": "key123",
            "schedule_enabled": True,
            "daily_social_enabled": True,
            "daily_social_time": "08:00",
            "daily_social_platforms": ["linkedin"],
            "daily_social_series_length": 100,
        }
        defaults.update(overrides)
        return PostizConfig(**defaults)

    def _setup_journal(self, tmp_path, entry_date="2026-02-15"):
        """Create a minimal journal entry file."""
        journal_dir = tmp_path / "journal"
        journal_dir.mkdir(parents=True, exist_ok=True)
        entry = (
            f"---\ndate: {entry_date}\n---\n\n"
            "# Journal Entry\n\nBuilt a cool pipeline today."
        )
        (journal_dir / f"journal-{entry_date}.md").write_text(entry, encoding="utf-8")

    def test_skips_when_no_config(self, tmp_path):
        result = generate_daily_social(tmp_path, postiz_config=None)
        assert result == []

    def test_skips_when_disabled(self, tmp_path):
        config = self._make_config(daily_social_enabled=False)
        result = generate_daily_social(tmp_path, postiz_config=config)
        assert result == []

    def test_skips_when_already_posted(self, tmp_path):
        config = self._make_config()
        state = DailySocialState(day_number=5, last_posted_date="2026-02-15")
        _save_daily_social_state(state, tmp_path)

        result = generate_daily_social(
            tmp_path, postiz_config=config, target_date=date(2026, 2, 15)
        )
        assert result == []

    def test_skips_when_series_complete(self, tmp_path):
        config = self._make_config(daily_social_series_length=10)
        state = DailySocialState(day_number=10, last_posted_date="2026-02-14")
        _save_daily_social_state(state, tmp_path)

        result = generate_daily_social(
            tmp_path, postiz_config=config, target_date=date(2026, 2, 15)
        )
        assert result == []

    def test_skips_when_no_journal_entries(self, tmp_path):
        config = self._make_config()
        result = generate_daily_social(
            tmp_path, postiz_config=config, target_date=date(2026, 2, 15)
        )
        assert result == []

    def test_dry_run(self, tmp_path, capsys):
        config = self._make_config()
        self._setup_journal(tmp_path)
        result = generate_daily_social(
            tmp_path, postiz_config=config, dry_run=True, target_date=date(2026, 2, 15)
        )
        assert result == []
        captured = capsys.readouterr()
        assert "DRY RUN" in captured.out
        assert "Day 1/100" in captured.out

    @patch("distill.llm.call_claude")
    def test_generates_post_and_writes_file(self, mock_run, tmp_path):
        config = self._make_config(schedule_enabled=False)
        self._setup_journal(tmp_path)
        mock_run.return_value = "Today I learned about pipelines.\n\n#BuildInPublic"

        result = generate_daily_social(
            tmp_path, postiz_config=config, target_date=date(2026, 2, 15)
        )

        assert len(result) == 1
        assert "daily-social-2026-02-15.md" in str(result[0])
        assert result[0].exists()
        content = result[0].read_text(encoding="utf-8")
        assert "pipelines" in content

    @patch("distill.llm.call_claude")
    def test_increments_day_counter(self, mock_run, tmp_path):
        config = self._make_config(schedule_enabled=False)
        self._setup_journal(tmp_path)
        mock_run.return_value = "Post content"

        # Pre-set state at day 5
        state = DailySocialState(day_number=5, last_posted_date="2026-02-14")
        _save_daily_social_state(state, tmp_path)

        generate_daily_social(
            tmp_path, postiz_config=config, target_date=date(2026, 2, 15)
        )

        updated = _load_daily_social_state(tmp_path)
        assert updated.day_number == 6
        assert updated.last_posted_date == "2026-02-15"

    @patch("distill.llm.call_claude")
    def test_day_counter_in_prompt(self, mock_run, tmp_path):
        config = self._make_config(schedule_enabled=False)
        self._setup_journal(tmp_path)
        mock_run.return_value = "Post content"

        state = DailySocialState(day_number=41, last_posted_date="2026-02-14")
        _save_daily_social_state(state, tmp_path)

        generate_daily_social(
            tmp_path, postiz_config=config, target_date=date(2026, 2, 15)
        )

        # call_claude is called: 1x story selector + 1x per-platform
        # The day counter is in the per-platform prompt (second call)
        assert mock_run.call_count >= 2
        platform_call_args = mock_run.call_args_list[1][0]  # second call, positional args
        system_prompt = platform_call_args[0]
        user_prompt = platform_call_args[1]
        full_prompt = f"{system_prompt}\n{user_prompt}"
        assert "Day 42/100" in full_prompt

    @patch("distill.llm.call_claude")
    def test_saves_to_content_store(self, mock_run, tmp_path):
        """Verify daily social saves content to ContentStore (Postiz push is gated)."""
        config = self._make_config()
        self._setup_journal(tmp_path)
        mock_run.return_value = "LinkedIn post content"

        generate_daily_social(
            tmp_path, postiz_config=config, target_date=date(2026, 2, 15)
        )

        # Verify content saved to ContentStore
        from distill.content import ContentStore

        store = ContentStore(tmp_path)
        record = store.get("daily-social-2026-02-15")
        assert record is not None
        assert record.status.value == "draft"
        assert "LinkedIn post content" in record.body

    @patch("distill.llm.call_claude")
    def test_force_regenerates(self, mock_run, tmp_path):
        config = self._make_config(schedule_enabled=False)
        self._setup_journal(tmp_path)
        mock_run.return_value = "Regenerated content"

        # Already posted today
        state = DailySocialState(day_number=5, last_posted_date="2026-02-15")
        _save_daily_social_state(state, tmp_path)

        result = generate_daily_social(
            tmp_path, postiz_config=config, force=True, target_date=date(2026, 2, 15)
        )

        assert len(result) == 1

        # Day counter should NOT increment on force re-gen of same date
        updated = _load_daily_social_state(tmp_path)
        assert updated.day_number == 5

    @patch("distill.llm.call_claude")
    def test_falls_back_to_recent_entry(self, mock_run, tmp_path):
        config = self._make_config(schedule_enabled=False)
        # Create an entry for yesterday, not today
        self._setup_journal(tmp_path, entry_date="2026-02-14")
        mock_run.return_value = "Post content"

        result = generate_daily_social(
            tmp_path, postiz_config=config, target_date=date(2026, 2, 15)
        )

        assert len(result) == 1

    @patch("distill.llm.call_claude")
    def test_skips_stale_entry(self, mock_run, tmp_path):
        config = self._make_config(schedule_enabled=False)
        # Create an entry from a week ago
        self._setup_journal(tmp_path, entry_date="2026-02-08")
        mock_run.return_value = "Post content"

        result = generate_daily_social(
            tmp_path, postiz_config=config, target_date=date(2026, 2, 15)
        )

        assert result == []


class TestDailySocialScheduling:
    def test_next_daily_social_slot(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo

        from distill.integrations.scheduling import next_daily_social_slot

        config = PostizConfig(
            url="https://postiz.test",
            api_key="key",
            daily_social_time="08:00",
            timezone="America/Chicago",
        )
        ref = datetime(2026, 2, 15, 14, 30, tzinfo=ZoneInfo("America/Chicago"))
        slot = next_daily_social_slot(config, reference=ref)

        assert "2026-02-16" in slot
        assert "08:00:00" in slot

    def test_next_daily_social_slot_always_tomorrow(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo

        from distill.integrations.scheduling import next_daily_social_slot

        config = PostizConfig(
            url="https://postiz.test",
            api_key="key",
            daily_social_time="08:00",
            timezone="America/Chicago",
        )
        # Even if it's 3am (before the daily social time), still schedules tomorrow
        ref = datetime(2026, 2, 15, 3, 0, tzinfo=ZoneInfo("America/Chicago"))
        slot = next_daily_social_slot(config, reference=ref)
        assert "2026-02-16" in slot


class TestDailySocialConfig:
    def test_postiz_config_daily_fields(self):
        cfg = PostizConfig(
            daily_social_enabled=True,
            daily_social_time="07:30",
            daily_social_platforms=["linkedin", "twitter"],
            daily_social_series_length=50,
        )
        assert cfg.daily_social_enabled is True
        assert cfg.daily_social_time == "07:30"
        assert cfg.daily_social_platforms == ["linkedin", "twitter"]
        assert cfg.daily_social_series_length == 50

    def test_postiz_config_daily_defaults(self):
        cfg = PostizConfig()
        assert cfg.daily_social_enabled is False
        assert cfg.daily_social_time == "08:00"
        assert cfg.daily_social_platforms == ["linkedin"]
        assert cfg.daily_social_series_length == 100

    def test_from_env_daily_social(self, monkeypatch):
        monkeypatch.setenv("POSTIZ_URL", "https://postiz.test")
        monkeypatch.setenv("POSTIZ_API_KEY", "key")
        monkeypatch.setenv("POSTIZ_DAILY_SOCIAL_ENABLED", "true")
        monkeypatch.setenv("POSTIZ_DAILY_SOCIAL_TIME", "07:30")
        monkeypatch.setenv("POSTIZ_DAILY_SOCIAL_PLATFORMS", "linkedin,twitter")
        monkeypatch.setenv("POSTIZ_DAILY_SOCIAL_SERIES_LENGTH", "50")
        cfg = PostizConfig.from_env()
        assert cfg.daily_social_enabled is True
        assert cfg.daily_social_time == "07:30"
        assert cfg.daily_social_platforms == ["linkedin", "twitter"]
        assert cfg.daily_social_series_length == 50

    def test_from_env_daily_defaults(self, monkeypatch):
        monkeypatch.delenv("POSTIZ_DAILY_SOCIAL_ENABLED", raising=False)
        monkeypatch.delenv("POSTIZ_DAILY_SOCIAL_TIME", raising=False)
        monkeypatch.delenv("POSTIZ_DAILY_SOCIAL_PLATFORMS", raising=False)
        monkeypatch.delenv("POSTIZ_DAILY_SOCIAL_SERIES_LENGTH", raising=False)
        monkeypatch.delenv("POSTIZ_URL", raising=False)
        monkeypatch.delenv("POSTIZ_API_KEY", raising=False)
        cfg = PostizConfig.from_env()
        assert cfg.daily_social_enabled is False
        assert cfg.daily_social_platforms == ["linkedin"]
        assert cfg.daily_social_series_length == 100

    def test_toml_config_daily_fields(self):
        from distill.config import DistillConfig, PostizSectionConfig

        config = DistillConfig(
            postiz=PostizSectionConfig(
                url="https://postiz.test",
                api_key="key",
                daily_social_enabled=True,
                daily_social_time="07:30",
                daily_social_platforms=["linkedin"],
                daily_social_series_length=50,
            )
        )
        postiz = config.to_postiz_config()
        assert postiz.daily_social_enabled is True
        assert postiz.daily_social_time == "07:30"
        assert postiz.daily_social_series_length == 50

    def test_toml_load_daily_social(self, tmp_path):
        from distill.config import load_config

        toml_content = """\
[postiz]
url = "https://postiz.test"
api_key = "key"
daily_social_enabled = true
daily_social_time = "07:30"
daily_social_platforms = ["linkedin", "twitter"]
daily_social_series_length = 50
"""
        toml_path = tmp_path / ".distill.toml"
        toml_path.write_text(toml_content, encoding="utf-8")

        config = load_config(toml_path)
        assert config.postiz.daily_social_enabled is True
        assert config.postiz.daily_social_time == "07:30"
        assert config.postiz.daily_social_platforms == ["linkedin", "twitter"]
        assert config.postiz.daily_social_series_length == 50


class TestFetchTroopxHighlights:
    """Tests for _fetch_troopx_highlights."""

    def test_returns_empty_when_psycopg2_missing(self):
        with patch("distill.pipeline.social._HAS_PSYCOPG2", False):
            result = _fetch_troopx_highlights(datetime(2026, 2, 22), "postgres://localhost/test")
            assert result == ""

    def test_returns_empty_when_no_db_url(self):
        result = _fetch_troopx_highlights(datetime(2026, 2, 22), "")
        assert result == ""

    @patch("distill.pipeline.social._HAS_PSYCOPG2", True)
    @patch("distill.pipeline.social.psycopg2")
    def test_returns_empty_on_connection_failure(self, mock_pg):
        mock_pg.connect.side_effect = Exception("Connection refused")
        result = _fetch_troopx_highlights(datetime(2026, 2, 22), "postgres://localhost/bad")
        assert result == ""

    @patch("distill.pipeline.social._HAS_PSYCOPG2", True)
    @patch("distill.pipeline.social.psycopg2")
    def test_formats_workflows_and_meetings(self, mock_pg):
        mock_conn = MagicMock()
        mock_pg.connect.return_value = mock_conn
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        # Workflow query returns 1 workflow
        workflow_rows = [
            ("wf-001", "Build health endpoint", "completed",
             datetime(2026, 2, 22, 10, 0), datetime(2026, 2, 22, 10, 30))
        ]
        # Blackboard for wf-001
        bb_rows = [("findings", "api-response", "Status 200 OK", "dev")]
        # Escalations for wf-001
        esc_rows = [("Need approval for deploy", "approved")]
        # Meetings
        meeting_rows = [("Sprint Planning", "Discussed Q1 goals and priorities", "concluded")]

        # Set up cursor.fetchall to return different results for each query
        mock_cursor.fetchall.side_effect = [
            workflow_rows,  # workflows query
            bb_rows,        # blackboard query
            esc_rows,       # escalations query
            meeting_rows,   # meetings query
        ]

        result = _fetch_troopx_highlights(datetime(2026, 2, 22), "postgres://localhost/test")

        assert "## TroopX Activity" in result
        assert "Build health endpoint" in result
        assert "completed" in result
        assert "Key finding:" in result
        assert "Escalation:" in result
        assert "Sprint Planning" in result

    @patch("distill.pipeline.social._HAS_PSYCOPG2", True)
    @patch("distill.pipeline.social.psycopg2")
    def test_prioritizes_failures(self, mock_pg):
        mock_conn = MagicMock()
        mock_pg.connect.return_value = mock_conn
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        # Two workflows: one completed, one failed
        workflow_rows = [
            ("wf-001", "Successful task", "completed",
             datetime(2026, 2, 22, 10, 0), datetime(2026, 2, 22, 10, 30)),
            ("wf-002", "Failed deploy", "failed",
             datetime(2026, 2, 22, 11, 0), datetime(2026, 2, 22, 11, 5)),
        ]

        mock_cursor.fetchall.side_effect = [
            workflow_rows,
            [],  # bb for wf-001
            [],  # esc for wf-001
            [],  # bb for wf-002
            [],  # esc for wf-002
            [],  # meetings
        ]

        result = _fetch_troopx_highlights(datetime(2026, 2, 22), "postgres://localhost/test")

        # Failed workflow should appear before successful one
        failed_pos = result.find("Failed deploy")
        success_pos = result.find("Successful task")
        assert failed_pos < success_pos

    @patch("distill.pipeline.social._HAS_PSYCOPG2", True)
    @patch("distill.pipeline.social.psycopg2")
    def test_caps_at_limits(self, mock_pg):
        mock_conn = MagicMock()
        mock_pg.connect.return_value = mock_conn
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        # 8 workflows — should be capped to 5
        workflow_rows = [
            (f"wf-{i:03d}", f"Task {i}", "completed",
             datetime(2026, 2, 22, 10, 0), datetime(2026, 2, 22, 10, 30))
            for i in range(8)
        ]

        # Build side_effect: workflow query, then per-workflow bb + esc, then meetings
        side_effects: list[list] = [workflow_rows]
        for _ in range(8):
            side_effects.append([])  # bb
            side_effects.append([])  # esc
        side_effects.append([])  # meetings

        mock_cursor.fetchall.side_effect = side_effects

        result = _fetch_troopx_highlights(datetime(2026, 2, 22), "postgres://localhost/test")

        # Count workflow entries (each starts with **Task N**)
        task_mentions = [line for line in result.split("\n") if line.startswith("**Task")]
        assert len(task_mentions) <= 5


class TestSelectStory:
    """Tests for _select_story."""

    @patch("distill.shared.llm.call_claude")
    def test_returns_llm_response(self, mock_call):
        mock_call.return_value = "Today the agent team autonomously resolved a deploy conflict."
        result = _select_story("raw context here")
        assert result == "Today the agent team autonomously resolved a deploy conflict."

    @patch("distill.shared.llm.call_claude")
    def test_falls_back_on_error(self, mock_call):
        from distill.shared.llm import LLMError

        mock_call.side_effect = LLMError("API timeout")
        result = _select_story("raw context fallback text")
        assert result == "raw context fallback text"

    @patch("distill.shared.llm.call_claude")
    def test_passes_story_selector_prompt(self, mock_call):
        mock_call.return_value = "Selected story"
        _select_story("some context", model="haiku")
        call_args = mock_call.call_args
        assert call_args[0][0] == STORY_SELECTOR_PROMPT
        assert call_args[0][1] == "some context"
        assert call_args[1]["label"] == "story-selector"
        assert call_args[1]["model"] == "haiku"


class TestGenerateDailySocialWithTroopx:
    """Tests for TroopX + story selection integration in generate_daily_social."""

    def _make_config(self, **overrides):
        defaults = {
            "url": "https://postiz.test",
            "api_key": "key123",
            "schedule_enabled": False,
            "daily_social_enabled": True,
            "daily_social_platforms": ["linkedin"],
            "daily_social_series_length": 100,
        }
        defaults.update(overrides)
        return PostizConfig(**defaults)

    def _setup_journal(self, tmp_path, entry_date="2026-02-15"):
        journal_dir = tmp_path / "journal"
        journal_dir.mkdir(parents=True, exist_ok=True)
        entry = (
            f"---\ndate: {entry_date}\n---\n\n"
            "# Journal Entry\n\nBuilt a cool agent pipeline today."
        )
        (journal_dir / f"journal-{entry_date}.md").write_text(entry, encoding="utf-8")

    @patch("distill.llm.call_claude")
    @patch("distill.pipeline.social._fetch_troopx_highlights")
    @patch("distill.shared.config.load_config")
    def test_includes_troopx_when_configured(self, mock_cfg, mock_fetch, mock_call, tmp_path):
        from distill.shared.config import DistillConfig, TroopXSectionConfig

        mock_cfg.return_value = DistillConfig(
            troopx=TroopXSectionConfig(db_url="postgres://localhost/troopx")
        )
        mock_fetch.return_value = "## TroopX Activity\n### Workflows (1 completed, 0 failed)"
        mock_call.return_value = "Post content"

        config = self._make_config()
        self._setup_journal(tmp_path)

        generate_daily_social(
            tmp_path, postiz_config=config, target_date=date(2026, 2, 15)
        )

        # _fetch_troopx_highlights should have been called
        mock_fetch.assert_called_once()
        # call_claude should have been called at least 2 times:
        # 1x story selector + 1x per-platform
        assert mock_call.call_count >= 2

    @patch("distill.llm.call_claude")
    @patch("distill.shared.config.load_config")
    def test_story_selector_runs(self, mock_cfg, mock_call, tmp_path):
        from distill.shared.config import DistillConfig

        mock_cfg.return_value = DistillConfig()
        mock_call.return_value = "Post content"

        config = self._make_config()
        self._setup_journal(tmp_path)

        generate_daily_social(
            tmp_path, postiz_config=config, target_date=date(2026, 2, 15)
        )

        # call_claude should be called: 1x story selector + 1x linkedin platform
        assert mock_call.call_count == 2
        # First call should be story selector
        first_call = mock_call.call_args_list[0]
        assert first_call[0][0] == STORY_SELECTOR_PROMPT

    @patch("distill.llm.call_claude")
    @patch("distill.shared.config.load_config")
    def test_works_without_troopx(self, mock_cfg, mock_call, tmp_path):
        from distill.shared.config import DistillConfig

        mock_cfg.return_value = DistillConfig()  # no troopx db_url
        mock_call.return_value = "Post without troopx"

        config = self._make_config()
        self._setup_journal(tmp_path)

        result = generate_daily_social(
            tmp_path, postiz_config=config, target_date=date(2026, 2, 15)
        )

        assert len(result) == 1
        content = result[0].read_text(encoding="utf-8")
        assert "troopx" not in content.lower() or "Post without troopx" in content
