"""Ghost CMS-compatible markdown publisher with optional live API publishing."""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from pathlib import Path

from distill.blog.config import GhostConfig
from distill.blog.context import ThematicBlogContext, WeeklyBlogContext
from distill.blog.publishers.base import BlogPublisher
from distill.blog.state import BlogState

logger = logging.getLogger(__name__)


class GhostAPIClient:
    """Client for the Ghost Admin API.

    Handles JWT authentication and post creation via urllib.
    """

    def __init__(self, config: GhostConfig) -> None:
        self.config = config
        self.base_url = config.url.rstrip("/")

    def _generate_token(self) -> str:
        """Generate a JWT token for Ghost Admin API authentication."""
        import jwt

        key_id, secret = self.config.admin_api_key.split(":")
        iat = int(time.time())
        payload = {
            "iat": iat,
            "exp": iat + 5 * 60,
            "aud": "/admin/",
        }
        return jwt.encode(
            payload,
            bytes.fromhex(secret),
            algorithm="HS256",
            headers={"kid": key_id},
        )

    def _request(self, method: str, path: str, data: dict | None = None) -> dict:
        """Make an authenticated request to the Ghost Admin API."""
        url = f"{self.base_url}/ghost/api/admin{path}"
        token = self._generate_token()

        body = json.dumps(data).encode("utf-8") if data else None
        req = urllib.request.Request(
            url,
            data=body,
            method=method,
            headers={
                "Authorization": f"Ghost {token}",
                "Content-Type": "application/json",
            },
        )

        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))

    @staticmethod
    def _markdown_to_mobiledoc(markdown: str) -> str:
        """Wrap markdown in Ghost's mobiledoc format for proper rendering."""
        json.dumps(markdown)
        mobiledoc = {
            "version": "0.3.1",
            "ghostVersion": "4.0",
            "markups": [],
            "atoms": [],
            "cards": [["markdown", {"markdown": markdown}]],
            "sections": [[10, 0]],
        }
        return json.dumps(mobiledoc)

    def create_post(
        self,
        title: str,
        markdown: str,
        tags: list[str] | None = None,
        status: str = "draft",
    ) -> dict:
        """Create a post in Ghost.

        Args:
            title: Post title.
            markdown: Post content as markdown.
            tags: List of tag names.
            status: "draft" or "published".

        Returns:
            The created post dict from Ghost API.
        """
        post_data: dict = {
            "title": title,
            "mobiledoc": self._markdown_to_mobiledoc(markdown),
            "status": status,
        }
        if tags:
            post_data["tags"] = [{"name": t} for t in tags]

        result = self._request("POST", "/posts/", {"posts": [post_data]})
        return result["posts"][0]

    def publish_with_newsletter(self, post_id: str, newsletter_slug: str) -> dict:
        """Publish a draft post and trigger newsletter delivery.

        Ghost requires a two-step flow:
        1. Create as draft
        2. PUT update with status=published and ?newsletter={slug}

        Args:
            post_id: The Ghost post ID.
            newsletter_slug: The newsletter slug to send to.

        Returns:
            The updated post dict from Ghost API.
        """
        path = f"/posts/{post_id}/?newsletter={newsletter_slug}"
        result = self._request("PUT", path, {"posts": [{"status": "published"}]})
        return result["posts"][0]


class GhostPublisher(BlogPublisher):
    """Formats blog posts as Ghost-compatible markdown.

    Generates clean markdown suitable for Ghost's Admin API markdown field.
    Metadata is embedded as an HTML comment at the top of the file for
    later consumption by a Ghost API integration.

    When a GhostConfig with credentials is provided, also publishes
    directly to the Ghost Admin API.
    """

    def __init__(self, ghost_config: GhostConfig | None = None) -> None:
        self._config = ghost_config
        self._api: GhostAPIClient | None = None
        if ghost_config and ghost_config.is_configured:
            self._api = GhostAPIClient(ghost_config)

    def format_weekly(self, context: WeeklyBlogContext, prose: str) -> str:
        meta = self._weekly_meta(context)
        content = meta + prose + "\n"
        self._publish_to_api(content)
        return content

    def format_thematic(self, context: ThematicBlogContext, prose: str) -> str:
        meta = self._thematic_meta(context)
        content = meta + prose + "\n"
        self._publish_to_api(content)
        return content

    def weekly_output_path(self, output_dir: Path, year: int, week: int) -> Path:
        return output_dir / "blog" / "ghost" / "weekly" / f"weekly-{year}-W{week:02d}.md"

    def thematic_output_path(self, output_dir: Path, slug: str) -> Path:
        return output_dir / "blog" / "ghost" / "themes" / f"{slug}.md"

    def format_index(self, output_dir: Path, state: BlogState) -> str:
        lines: list[str] = ["# Blog Posts", ""]

        weekly = sorted(
            [p for p in state.posts if p.post_type == "weekly"],
            key=lambda p: p.slug,
            reverse=True,
        )
        if weekly:
            lines.append("## Weekly")
            lines.append("")
            for post in weekly:
                date_str = post.generated_at.strftime("%Y-%m-%d")
                lines.append(f"- [{post.slug}](weekly/{post.slug}.md) ({date_str})")
            lines.append("")

        thematic = sorted(
            [p for p in state.posts if p.post_type == "thematic"],
            key=lambda p: p.slug,
        )
        if thematic:
            lines.append("## Thematic")
            lines.append("")
            for post in thematic:
                date_str = post.generated_at.strftime("%Y-%m-%d")
                lines.append(f"- [{post.slug}](themes/{post.slug}.md) ({date_str})")
            lines.append("")

        return "\n".join(lines)

    def index_path(self, output_dir: Path) -> Path:
        return output_dir / "blog" / "ghost" / "index.md"

    def _weekly_meta(self, context: WeeklyBlogContext) -> str:
        meta = {
            "title": f"Week {context.year}-W{context.week:02d} Synthesis",
            "tags": ["blog", "weekly"]
            + [t for t in context.all_tags[:8] if t not in ("blog", "weekly")],
            "status": "draft",
        }
        return f"<!-- ghost-meta: {json.dumps(meta)} -->\n\n"

    def _thematic_meta(self, context: ThematicBlogContext) -> str:
        meta = {
            "title": context.theme.title,
            "tags": ["blog", "thematic"] + list(context.theme.slug.split("-")),
            "status": "draft",
        }
        return f"<!-- ghost-meta: {json.dumps(meta)} -->\n\n"

    def _parse_ghost_meta(self, content: str) -> dict:
        """Extract ghost-meta JSON from content."""
        if "<!-- ghost-meta:" not in content:
            return {}
        try:
            meta_str = content.split("<!-- ghost-meta:")[1].split("-->")[0].strip()
            return json.loads(meta_str)
        except (IndexError, json.JSONDecodeError):
            return {}

    def _publish_to_api(self, content: str) -> dict | None:
        """Publish content to Ghost API if configured.

        Returns the API response dict, or None if not configured or on error.
        """
        if not self._api or not self._config:
            return None

        meta = self._parse_ghost_meta(content)
        if not meta:
            return None

        title = meta.get("title", "Untitled")
        tags = meta.get("tags", [])

        # Strip the ghost-meta comment from content before publishing
        prose = content.split("-->\n\n", 1)[-1] if "-->\n\n" in content else content

        try:
            if self._config.newsletter_slug:
                # Two-step: create draft, then publish with newsletter
                post = self._api.create_post(title, prose, tags, status="draft")
                post = self._api.publish_with_newsletter(post["id"], self._config.newsletter_slug)
                logger.info("Published '%s' to Ghost with newsletter", title)
                return post
            else:
                # Single step: create as published or draft
                status = "published" if self._config.auto_publish else "draft"
                post = self._api.create_post(title, prose, tags, status=status)
                logger.info("Published '%s' to Ghost as %s", title, status)
                return post
        except (urllib.error.URLError, Exception):
            logger.warning("Failed to publish '%s' to Ghost API", title, exc_info=True)
            return None
