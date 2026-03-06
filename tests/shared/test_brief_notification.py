"""Tests for brief notification sending."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from distill.brief.models import DraftPost, ReadingBrief, ReadingHighlight
from distill.shared.config import NotificationConfig
from distill.shared.notifications import send_brief_notification


@pytest.fixture
def config():
    return NotificationConfig(ntfy_url="https://ntfy.sh", ntfy_topic="test")


@pytest.fixture
def brief():
    return ReadingBrief(
        date="2026-03-05",
        highlights=[
            ReadingHighlight(title="AI Agents", source="blog.example", summary="Agents are evolving"),
            ReadingHighlight(title="Rust in 2026", source="rust-lang.org", summary="New features"),
            ReadingHighlight(title="LLM Eval", source="arxiv", summary="Better benchmarks"),
        ],
        drafts=[DraftPost(platform="linkedin", content="test", char_count=4)],
    )


def test_sends_ntfy_brief(config, brief):
    with patch("distill.shared.notifications.urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        send_brief_notification(config, brief)
        mock_urlopen.assert_called_once()
        req = mock_urlopen.call_args[0][0]
        assert "AI Agents" in req.data.decode()
        assert req.get_header("Title") == "Distill — 2026-03-05"
        assert req.get_header("Tags") == "newspaper,sparkles"


def test_skips_when_not_configured(brief):
    config = NotificationConfig()
    with patch("distill.shared.notifications.urllib.request.urlopen") as mock_urlopen:
        send_brief_notification(config, brief)
        mock_urlopen.assert_not_called()


def test_skips_when_no_highlights(config):
    brief = ReadingBrief(date="2026-03-05")
    with patch("distill.shared.notifications.urllib.request.urlopen") as mock_urlopen:
        send_brief_notification(config, brief)
        mock_urlopen.assert_not_called()


def test_includes_dashboard_action(config, brief):
    with patch("distill.shared.notifications.urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        send_brief_notification(config, brief, dashboard_url="http://localhost:6107/")
        req = mock_urlopen.call_args[0][0]
        assert "Open Daily View" in req.get_header("Actions")


def test_includes_draft_count(config, brief):
    with patch("distill.shared.notifications.urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        send_brief_notification(config, brief)
        body = mock_urlopen.call_args[0][0].data.decode()
        assert "1 draft post(s) ready" in body
