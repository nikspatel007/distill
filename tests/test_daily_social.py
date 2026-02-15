"""Tests for the daily social post generation pipeline."""

import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from distill.core import (
    DAILY_SOCIAL_STATE_FILENAME,
    DailySocialState,
    _load_daily_social_state,
    _save_daily_social_state,
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

    @patch("distill.blog.synthesizer.subprocess.run")
    def test_generates_post_and_writes_file(self, mock_run, tmp_path):
        config = self._make_config(schedule_enabled=False)
        self._setup_journal(tmp_path)
        mock_run.return_value = _make_subprocess_result(
            "Today I learned about pipelines.\n\n#BuildInPublic"
        )

        result = generate_daily_social(
            tmp_path, postiz_config=config, target_date=date(2026, 2, 15)
        )

        assert len(result) == 1
        assert "daily-social-2026-02-15.md" in str(result[0])
        assert result[0].exists()
        content = result[0].read_text(encoding="utf-8")
        assert "pipelines" in content

    @patch("distill.blog.synthesizer.subprocess.run")
    def test_increments_day_counter(self, mock_run, tmp_path):
        config = self._make_config(schedule_enabled=False)
        self._setup_journal(tmp_path)
        mock_run.return_value = _make_subprocess_result()

        # Pre-set state at day 5
        state = DailySocialState(day_number=5, last_posted_date="2026-02-14")
        _save_daily_social_state(state, tmp_path)

        generate_daily_social(
            tmp_path, postiz_config=config, target_date=date(2026, 2, 15)
        )

        updated = _load_daily_social_state(tmp_path)
        assert updated.day_number == 6
        assert updated.last_posted_date == "2026-02-15"

    @patch("distill.blog.synthesizer.subprocess.run")
    def test_day_counter_in_prompt(self, mock_run, tmp_path):
        config = self._make_config(schedule_enabled=False)
        self._setup_journal(tmp_path)
        mock_run.return_value = _make_subprocess_result()

        state = DailySocialState(day_number=41, last_posted_date="2026-02-14")
        _save_daily_social_state(state, tmp_path)

        generate_daily_social(
            tmp_path, postiz_config=config, target_date=date(2026, 2, 15)
        )

        # The prompt is the last positional arg to subprocess.run's first arg (the cmd list)
        call_args = mock_run.call_args[0][0]  # cmd list
        full_prompt = call_args[-1]  # last element is the prompt
        assert "Day 42/100" in full_prompt

    @patch("distill.integrations.postiz.urllib.request.urlopen")
    @patch("distill.blog.synthesizer.subprocess.run")
    def test_pushes_to_postiz(self, mock_run, mock_urlopen, tmp_path):
        config = self._make_config()
        self._setup_journal(tmp_path)
        mock_run.return_value = _make_subprocess_result("LinkedIn post content")

        # Mock urlopen for both list_integrations and create_post calls
        # First call: list_integrations, second+: create_post
        responses = [
            # list_integrations (called by resolve_integration_ids, then again by create_post)
            json.dumps([
                {"id": "int-1", "name": "LinkedIn", "providerIdentifier": "linkedin"},
            ]).encode(),
            # list_integrations again (called inside create_post)
            json.dumps([
                {"id": "int-1", "name": "LinkedIn", "providerIdentifier": "linkedin"},
            ]).encode(),
            # create_post response
            json.dumps({"id": "post-1"}).encode(),
        ]
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read = MagicMock(side_effect=responses)
        mock_urlopen.return_value = mock_resp

        generate_daily_social(
            tmp_path, postiz_config=config, target_date=date(2026, 2, 15)
        )

        # Verify at least 2 urlopen calls (list_integrations + create_post)
        assert mock_urlopen.call_count >= 2

    @patch("distill.blog.synthesizer.subprocess.run")
    def test_force_regenerates(self, mock_run, tmp_path):
        config = self._make_config(schedule_enabled=False)
        self._setup_journal(tmp_path)
        mock_run.return_value = _make_subprocess_result("Regenerated content")

        # Already posted today
        state = DailySocialState(day_number=5, last_posted_date="2026-02-15")
        _save_daily_social_state(state, tmp_path)

        result = generate_daily_social(
            tmp_path, postiz_config=config, force=True, target_date=date(2026, 2, 15)
        )

        assert len(result) == 1

    @patch("distill.blog.synthesizer.subprocess.run")
    def test_falls_back_to_recent_entry(self, mock_run, tmp_path):
        config = self._make_config(schedule_enabled=False)
        # Create an entry for yesterday, not today
        self._setup_journal(tmp_path, entry_date="2026-02-14")
        mock_run.return_value = _make_subprocess_result()

        result = generate_daily_social(
            tmp_path, postiz_config=config, target_date=date(2026, 2, 15)
        )

        assert len(result) == 1

    @patch("distill.blog.synthesizer.subprocess.run")
    def test_skips_stale_entry(self, mock_run, tmp_path):
        config = self._make_config(schedule_enabled=False)
        # Create an entry from a week ago
        self._setup_journal(tmp_path, entry_date="2026-02-08")
        mock_run.return_value = _make_subprocess_result()

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
