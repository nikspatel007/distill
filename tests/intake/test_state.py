"""Tests for intake state tracking."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from distill.intake.state import (
    IntakeRecord,
    IntakeState,
    load_intake_state,
    save_intake_state,
)


class TestIntakeState:
    def test_empty(self):
        state = IntakeState()
        assert state.records == []
        assert state.last_run is None

    def test_is_processed(self):
        state = IntakeState()
        assert state.is_processed("abc") is False

        state.mark_processed(IntakeRecord(item_id="abc", title="Test"))
        assert state.is_processed("abc") is True

    def test_mark_processed_upserts(self):
        state = IntakeState()
        state.mark_processed(IntakeRecord(item_id="abc", title="V1"))
        state.mark_processed(IntakeRecord(item_id="abc", title="V2"))
        assert len(state.records) == 1
        assert state.records[0].title == "V2"

    def test_prune(self):
        state = IntakeState()
        old = IntakeRecord(
            item_id="old",
            processed_at=datetime(2020, 1, 1),
        )
        recent = IntakeRecord(item_id="new")
        state.records = [old, recent]
        state.prune(keep_days=30)
        assert len(state.records) == 1
        assert state.records[0].item_id == "new"


class TestStatePersistence:
    def test_save_and_load(self, tmp_path):
        state = IntakeState()
        state.mark_processed(IntakeRecord(item_id="x", title="Test"))
        state.last_run = datetime(2026, 2, 7, 12, 0)

        save_intake_state(state, tmp_path)
        loaded = load_intake_state(tmp_path)

        assert loaded.is_processed("x") is True
        assert loaded.last_run is not None

    def test_load_missing(self, tmp_path):
        state = load_intake_state(tmp_path)
        assert state.records == []

    def test_load_corrupt(self, tmp_path):
        state_path = tmp_path / "intake" / ".intake-state.json"
        state_path.parent.mkdir(parents=True)
        state_path.write_text("not json", encoding="utf-8")

        state = load_intake_state(tmp_path)
        assert state.records == []

    def test_creates_directory(self, tmp_path):
        state = IntakeState()
        save_intake_state(state, tmp_path)
        assert (tmp_path / "intake" / ".intake-state.json").exists()
