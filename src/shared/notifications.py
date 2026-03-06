"""Pipeline run notifications via Slack and ntfy.sh."""

from __future__ import annotations

import json
import logging
import urllib.request
from typing import TYPE_CHECKING
from urllib.error import URLError

from distill.shared.config import NotificationConfig
from distill.shared.errors import PipelineReport

if TYPE_CHECKING:
    from distill.brief.models import ReadingBrief

logger = logging.getLogger(__name__)


def send_notification(config: NotificationConfig, report: PipelineReport) -> None:
    """Send pipeline report notifications to configured channels.

    Args:
        config: Notification configuration (Slack webhook, ntfy URL/topic).
        report: The pipeline report to summarize.
    """
    if not config.is_configured:
        return

    if config.slack_webhook:
        _send_slack(config.slack_webhook, report)

    if config.ntfy_url:
        _send_ntfy(config.ntfy_url, config.ntfy_topic, report)


def send_brief_notification(
    config: NotificationConfig,
    brief: ReadingBrief,
    dashboard_url: str = "",
) -> None:
    """Send a reading brief notification via ntfy.

    Sends the top 3 highlights as a push notification with an optional
    action button to open the Daily View dashboard.
    """
    if not config.is_configured or not config.ntfy_url:
        return
    if not brief.highlights:
        return

    title = f"Distill — {brief.date}"
    lines = []
    for h in brief.highlights[:3]:
        lines.append(f"• {h.title}")
        if h.summary:
            lines.append(f"  {h.summary[:80]}")
    if brief.drafts:
        lines.append(f"\n{len(brief.drafts)} draft post(s) ready")
    body = "\n".join(lines)

    url = f"{config.ntfy_url.rstrip('/')}/{config.ntfy_topic}"
    headers: dict[str, str] = {
        "Title": title,
        "Priority": "default",
        "Tags": "newspaper,sparkles",
    }
    if dashboard_url:
        headers["Actions"] = f"view, Open Daily View, {dashboard_url}"

    req = urllib.request.Request(
        url,
        data=body.encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status != 200:
                logger.warning("ntfy brief returned status %d", resp.status)
    except (URLError, OSError) as exc:
        logger.warning("Failed to send brief notification: %s", exc)


def _send_slack(webhook_url: str, report: PipelineReport) -> None:
    """POST a message to a Slack webhook."""
    payload = json.dumps({"text": report.summary_text()}).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status != 200:
                logger.warning("Slack webhook returned status %d", resp.status)
    except (URLError, OSError) as exc:
        logger.warning("Failed to send Slack notification: %s", exc)


def _send_ntfy(base_url: str, topic: str, report: PipelineReport) -> None:
    """POST a message to ntfy.sh."""
    url = f"{base_url.rstrip('/')}/{topic}"
    status = "completed" if report.success else "failed"
    title = f"Distill pipeline {status}"
    body = report.summary_text().encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Title": title,
            "Priority": "default" if report.success else "high",
            "Tags": "white_check_mark" if report.success else "warning",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status != 200:
                logger.warning("ntfy returned status %d", resp.status)
    except (URLError, OSError) as exc:
        logger.warning("Failed to send ntfy notification: %s", exc)
