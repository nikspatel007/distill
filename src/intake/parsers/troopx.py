"""TroopX workflow and agent data parser."""

from __future__ import annotations

import hashlib
import logging
import os
from datetime import UTC, datetime, timedelta
from fnmatch import fnmatch
from pathlib import Path

from distill.intake.models import ContentItem, ContentSource, ContentType
from distill.intake.parsers.base import ContentParser

logger = logging.getLogger(__name__)

try:
    import psycopg2

    _HAS_PSYCOPG2 = True
except ImportError:
    psycopg2 = None  # type: ignore[assignment]
    _HAS_PSYCOPG2 = False


class TroopXParser(ContentParser):
    """Parses TroopX workflow data, blackboard entries, and agent memories."""

    @property
    def source(self) -> ContentSource:
        return ContentSource.TROOPX

    @property
    def is_configured(self) -> bool:
        return self._config.troopx.is_configured

    def parse(self, since: datetime | None = None) -> list[ContentItem]:
        if not self.is_configured:
            return []

        if since is None:
            since = datetime.now(tz=UTC) - timedelta(days=self._config.troopx.max_age_days)
        elif since.tzinfo is None:
            since = since.replace(tzinfo=UTC)

        items: list[ContentItem] = []
        seen_ids: set[str] = set()

        # Try DB-based parsing first
        if self._config.troopx.db_url and _HAS_PSYCOPG2:
            db_items = self._parse_from_db(since)
            for item in db_items:
                if item.id not in seen_ids:
                    seen_ids.add(item.id)
                    items.append(item)
        elif self._config.troopx.db_url and not _HAS_PSYCOPG2:
            logger.warning("psycopg2 not installed. pip install psycopg2-binary")

        # File-based parsing (always available)
        file_items = self._parse_from_files()
        for item in file_items:
            if item.id not in seen_ids:
                seen_ids.add(item.id)
                items.append(item)

        limit = self._config.max_items_per_source
        items = items[:limit]
        logger.info("Parsed %d items from TroopX", len(items))
        return items

    def _matches_workflow_filters(self, task_description: str) -> bool:
        """Check if a workflow matches include/exclude patterns."""
        include = self._config.troopx.include_workflows
        exclude = self._config.troopx.exclude_workflows

        if exclude:
            for pattern in exclude:
                if fnmatch(task_description.lower(), pattern.lower()):
                    return False

        if include:
            for pattern in include:
                if fnmatch(task_description.lower(), pattern.lower()):
                    return True
            return False

        return True

    def _parse_from_db(self, since: datetime) -> list[ContentItem]:
        """Parse workflows and meetings from PostgreSQL."""
        items: list[ContentItem] = []

        try:
            conn = psycopg2.connect(self._config.troopx.db_url)
            try:
                items.extend(self._query_workflows(conn, since))
                items.extend(self._query_meetings(conn, since))
            finally:
                conn.close()
        except Exception:
            logger.exception("Failed to connect to TroopX database")

        return items

    def _query_workflows(self, conn: object, since: datetime) -> list[ContentItem]:
        """Query workflow metadata + blackboard entries."""
        items: list[ContentItem] = []

        cur = conn.cursor()  # type: ignore[union-attr]
        try:
            cur.execute(
                """SELECT workflow_id, task_description, status, started_at, ended_at
                   FROM router_workflow_metadata
                   WHERE started_at >= %s
                   ORDER BY started_at DESC""",
                (since,),
            )
            workflows = cur.fetchall()

            for wf_id, task_desc, status, started_at, completed_at in workflows:
                if not self._matches_workflow_filters(task_desc or ""):
                    continue

                # Get blackboard entries for this workflow
                cur.execute(
                    """SELECT namespace, key, value, contributor_role, created_at
                       FROM blackboard_entries
                       WHERE workflow_id = %s
                       ORDER BY created_at""",
                    (wf_id,),
                )
                bb_rows = cur.fetchall()

                # Get signals
                cur.execute(
                    """SELECT signal_type, message, role, created_at
                       FROM router_signals
                       WHERE workflow_id = %s
                       ORDER BY created_at""",
                    (wf_id,),
                )
                signal_rows = cur.fetchall()

                # Get escalations
                cur.execute(
                    """SELECT reason, context, response_signal, created_at
                       FROM router_escalations
                       WHERE workflow_id = %s
                       ORDER BY created_at""",
                    (wf_id,),
                )
                escalation_rows = cur.fetchall()

                # Build body
                body = self._build_workflow_body(
                    task_desc, status, bb_rows, signal_rows, escalation_rows
                )

                # Extract agent roles from blackboard contributors
                roles = sorted({row[3] for row in bb_rows if row[3]})
                # Tags from blackboard namespaces
                namespaces = sorted({row[0] for row in bb_rows if row[0]})
                tags = ["troopx", f"status:{status}"] + namespaces

                duration = None
                if started_at and completed_at:
                    duration = int((completed_at - started_at).total_seconds())

                item_id = hashlib.sha256(f"troopx:{wf_id}".encode()).hexdigest()[:16]

                items.append(
                    ContentItem(
                        id=item_id,
                        title=task_desc or f"Workflow {wf_id[:8]}",
                        body=body,
                        word_count=len(body.split()),
                        author=", ".join(roles),
                        site_name="TroopX",
                        source=ContentSource.TROOPX,
                        source_id=wf_id,
                        content_type=ContentType.ARTICLE,
                        tags=tags,
                        published_at=started_at,
                        metadata={
                            "workflow_id": wf_id,
                            "status": status,
                            "duration_seconds": duration,
                            "agent_count": len(roles),
                            "blackboard_entries": len(bb_rows),
                            "signals": len(signal_rows),
                            "escalations": len(escalation_rows),
                        },
                    )
                )
        finally:
            cur.close()

        return items

    def _query_meetings(self, conn: object, since: datetime) -> list[ContentItem]:
        """Query meetings from the database."""
        items: list[ContentItem] = []

        cur = conn.cursor()  # type: ignore[union-attr]
        try:
            cur.execute(
                """SELECT meeting_id, topic, agenda, summary, creator_agent_id,
                          status, created_at, started_at, concluded_at
                   FROM meetings
                   WHERE created_at >= %s
                   ORDER BY created_at DESC""",
                (since,),
            )
            rows = cur.fetchall()

            for (
                meeting_id, topic, agenda, summary, creator_agent_id,
                status, created_at, started_at, concluded_at,
            ) in rows:
                body_parts = []
                if agenda:
                    body_parts.append(f"## Agenda\n\n{agenda}")
                if summary:
                    body_parts.append(f"## Summary\n\n{summary}")
                if creator_agent_id:
                    body_parts.append(f"**Created by**: {creator_agent_id}")
                if status:
                    body_parts.append(f"**Status**: {status}")
                body = "\n\n".join(body_parts)

                item_id = hashlib.sha256(f"troopx:meeting:{meeting_id}".encode()).hexdigest()[:16]

                items.append(
                    ContentItem(
                        id=item_id,
                        title=topic or f"Meeting {meeting_id}",
                        body=body,
                        word_count=len(body.split()),
                        site_name="TroopX",
                        source=ContentSource.TROOPX,
                        source_id=str(meeting_id),
                        content_type=ContentType.ARTICLE,
                        tags=["troopx", "meeting"],
                        published_at=created_at,
                        metadata={"meeting_id": str(meeting_id)},
                    )
                )
        finally:
            cur.close()

        return items

    @staticmethod
    def _build_workflow_body(
        task_desc: str,
        status: str,
        bb_rows: list[tuple],
        signal_rows: list[tuple],
        escalation_rows: list[tuple],
    ) -> str:
        """Assemble a workflow body with blackboard entries, signals, and escalations."""
        lines: list[str] = []

        lines.append(f"# {task_desc}")
        lines.append(f"\nStatus: **{status}**\n")

        # Group blackboard by namespace
        if bb_rows:
            namespaces: dict[str, list[tuple]] = {}
            for ns, key, value, role, created in bb_rows:
                namespaces.setdefault(ns, []).append((key, value, role, created))

            lines.append("## Blackboard\n")
            for ns, entries in sorted(namespaces.items()):
                lines.append(f"### {ns}\n")
                for key, value, role, _created in entries:
                    # Truncate long values
                    display_val = value if len(str(value)) <= 500 else str(value)[:500] + "..."
                    lines.append(f"**{key}** ({role}): {display_val}\n")

        if signal_rows:
            lines.append("## Signals\n")
            for signal, message, role, created in signal_rows:
                msg = f" — {message}" if message else ""
                lines.append(f"- **{signal}** from {role}{msg}")
            lines.append("")

        if escalation_rows:
            lines.append("## Human Escalations\n")
            for reason, context, response, created in escalation_rows:
                lines.append(f"- **Reason**: {reason}")
                if context:
                    lines.append(f"  Context: {context}")
                if response:
                    lines.append(f"  Response: {response}")
            lines.append("")

        return "\n".join(lines)

    def _parse_from_files(self) -> list[ContentItem]:
        """Parse agent memories and knowledge from the file system."""
        items: list[ContentItem] = []

        # Parse from project-level .troopx
        project_dir = self._config.troopx.troopx_project
        if project_dir:
            items.extend(self._parse_memory_files(Path(project_dir)))
            items.extend(self._parse_knowledge_files(Path(project_dir)))

        # Parse from home-level ~/.troopx
        home_dir = self._config.troopx.troopx_home
        if home_dir:
            home_path = Path(os.path.expanduser(home_dir))
            items.extend(self._parse_roster_files(home_path))

        return items

    def _parse_memory_files(self, project_dir: Path) -> list[ContentItem]:
        """Read MEMORY-{role}.md files from project .troopx/memory/."""
        items: list[ContentItem] = []
        memory_dir = project_dir / "memory"
        if not memory_dir.is_dir():
            return items

        for path in sorted(memory_dir.glob("MEMORY-*.md")):
            role = path.stem.replace("MEMORY-", "")
            body = path.read_text(encoding="utf-8", errors="replace")
            if not body.strip():
                continue

            item_id = hashlib.sha256(f"troopx:memory:{role}".encode()).hexdigest()[:16]

            items.append(
                ContentItem(
                    id=item_id,
                    title=f"Agent Memory: {role}",
                    body=body,
                    word_count=len(body.split()),
                    author=role,
                    site_name="TroopX",
                    source=ContentSource.TROOPX,
                    source_id=f"memory:{role}",
                    content_type=ContentType.ARTICLE,
                    tags=["troopx", "agent-memory", role],
                    metadata={"role": role, "file_path": str(path)},
                )
            )

        return items

    def _parse_knowledge_files(self, project_dir: Path) -> list[ContentItem]:
        """Read learnings.md from project .troopx/knowledge/."""
        items: list[ContentItem] = []
        knowledge_dir = project_dir / "knowledge"
        if not knowledge_dir.is_dir():
            return items

        learnings_path = knowledge_dir / "learnings.md"
        if learnings_path.is_file():
            body = learnings_path.read_text(encoding="utf-8", errors="replace")
            if body.strip():
                item_id = hashlib.sha256(b"troopx:knowledge:learnings").hexdigest()[:16]
                items.append(
                    ContentItem(
                        id=item_id,
                        title="TroopX Team Learnings",
                        body=body,
                        word_count=len(body.split()),
                        site_name="TroopX",
                        source=ContentSource.TROOPX,
                        source_id="knowledge:learnings",
                        content_type=ContentType.ARTICLE,
                        tags=["troopx", "knowledge", "learnings"],
                        metadata={"file_path": str(learnings_path)},
                    )
                )

        return items

    def _parse_roster_files(self, home_dir: Path) -> list[ContentItem]:
        """Read agent CLAUDE.md files from ~/.troopx/roster/{role}/."""
        items: list[ContentItem] = []
        roster_dir = home_dir / "roster"
        if not roster_dir.is_dir():
            return items

        for role_dir in sorted(roster_dir.iterdir()):
            if not role_dir.is_dir():
                continue
            claude_md = role_dir / "CLAUDE.md"
            if not claude_md.is_file():
                continue
            body = claude_md.read_text(encoding="utf-8", errors="replace")
            if not body.strip():
                continue

            role = role_dir.name
            item_id = hashlib.sha256(f"troopx:roster:{role}".encode()).hexdigest()[:16]

            items.append(
                ContentItem(
                    id=item_id,
                    title=f"Agent Identity: {role}",
                    body=body,
                    word_count=len(body.split()),
                    author=role,
                    site_name="TroopX",
                    source=ContentSource.TROOPX,
                    source_id=f"roster:{role}",
                    content_type=ContentType.ARTICLE,
                    tags=["troopx", "agent-identity", role],
                    metadata={"role": role, "file_path": str(claude_md)},
                )
            )

        return items
