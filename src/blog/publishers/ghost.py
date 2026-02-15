"""Ghost CMS-compatible markdown publisher with optional live API publishing."""

from __future__ import annotations

import base64
import json
import logging
import re
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

    def _request_multipart(self, path: str, file_path: Path, field: str = "file") -> dict:
        """Upload a file via multipart form POST to the Ghost Admin API.

        Args:
            path: API endpoint path (e.g. "/images/upload/").
            file_path: Local file to upload.
            field: Form field name for the file.

        Returns:
            Parsed JSON response from Ghost.
        """
        url = f"{self.base_url}/ghost/api/admin{path}"
        token = self._generate_token()

        boundary = "----DistillUploadBoundary"
        ext = file_path.suffix.lower()
        content_type = "image/png" if ext == ".png" else "image/jpeg"

        file_data = file_path.read_bytes()

        disposition = (
            f'Content-Disposition: form-data; name="{field}";'
            f' filename="{file_path.name}"\r\n'
        )
        body_parts: list[bytes] = [
            f"--{boundary}\r\n".encode(),
            disposition.encode(),
            f"Content-Type: {content_type}\r\n\r\n".encode(),
            file_data,
            f"\r\n--{boundary}--\r\n".encode(),
        ]
        body = b"".join(body_parts)

        req = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Ghost {token}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
        )

        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def upload_image(self, file_path: Path) -> str | None:
        """Upload an image to Ghost and return its URL.

        Args:
            file_path: Local image file to upload.

        Returns:
            The URL of the uploaded image, or None on any failure.
        """
        try:
            result = self._request_multipart("/images/upload/", file_path)
            return result["images"][0]["url"]
        except Exception:
            logger.warning("Failed to upload image '%s' to Ghost", file_path, exc_info=True)
            return None

    def create_post(
        self,
        title: str,
        markdown: str,
        tags: list[str] | None = None,
        status: str = "draft",
        feature_image: str | None = None,
    ) -> dict:
        """Create a post in Ghost.

        Args:
            title: Post title.
            markdown: Post content as markdown.
            tags: List of tag names.
            status: "draft" or "published".
            feature_image: Optional URL for the post's feature image.

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
        if feature_image:
            post_data["feature_image"] = feature_image

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
        self.last_post_url: str | None = None
        self.last_feature_image_url: str | None = None
        if ghost_config and ghost_config.is_configured:
            self._api = GhostAPIClient(ghost_config)

    def format_weekly(
        self,
        context: WeeklyBlogContext,
        prose: str,
        *,
        feature_image_path: Path | None = None,
    ) -> str:
        meta = self._weekly_meta(context)
        content = meta + prose + "\n"
        self._publish_to_api(content, feature_image_path=feature_image_path)
        return content

    def format_thematic(
        self,
        context: ThematicBlogContext,
        prose: str,
        *,
        feature_image_path: Path | None = None,
    ) -> str:
        meta = self._thematic_meta(context)
        content = meta + prose + "\n"
        self._publish_to_api(content, feature_image_path=feature_image_path)
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

    @staticmethod
    def _strip_leading_h1(prose: str) -> str:
        """Remove the first H1 heading line from prose.

        Ghost renders the title from API metadata, so leaving the H1 in the
        markdown body causes the title to appear twice.
        """
        lines = prose.split("\n")
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("# ") and not stripped.startswith("## "):
                return "\n".join(lines[:i] + lines[i + 1 :]).lstrip("\n")
            break  # first non-blank line is not H1, stop
        return prose

    _MERMAID_RE = re.compile(r"```mermaid\s*\n(.*?)```", re.DOTALL)

    @classmethod
    def _convert_mermaid_to_images(cls, prose: str) -> str:
        """Replace ```mermaid blocks with mermaid.ink image URLs.

        Ghost doesn't render mermaid natively, so we convert each block
        to an image via the mermaid.ink service (base64-encoded).
        """

        def _replace(match: re.Match[str]) -> str:
            code = match.group(1).strip()
            encoded = base64.urlsafe_b64encode(code.encode("utf-8")).decode("ascii")
            url = f"https://mermaid.ink/img/{encoded}"
            return f"![diagram]({url})"

        return cls._MERMAID_RE.sub(_replace, prose)

    def _publish_to_api(
        self, content: str, *, feature_image_path: Path | None = None
    ) -> dict | None:
        """Publish content to Ghost API if configured.

        Args:
            content: Full post content with ghost-meta comment.
            feature_image_path: Optional local image to upload as feature image.

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
        # Strip H1 heading (Ghost renders title from metadata)
        prose = self._strip_leading_h1(prose)
        # Convert mermaid code blocks to rendered images
        prose = self._convert_mermaid_to_images(prose)

        # Upload feature image if provided
        feature_image_url: str | None = None
        if feature_image_path and feature_image_path.exists():
            feature_image_url = self._api.upload_image(feature_image_path)

        try:
            if self._config.newsletter_slug:
                # Two-step: create draft, then publish with newsletter
                post = self._api.create_post(
                    title, prose, tags, status="draft", feature_image=feature_image_url
                )
                post = self._api.publish_with_newsletter(post["id"], self._config.newsletter_slug)
                logger.info("Published '%s' to Ghost with newsletter", title)
            else:
                # Single step: create as published or draft
                status = "published" if self._config.auto_publish else "draft"
                post = self._api.create_post(
                    title, prose, tags, status=status, feature_image=feature_image_url
                )
                logger.info("Published '%s' to Ghost as %s", title, status)
            # Capture canonical URL and feature image for downstream publishers
            self.last_post_url = post.get("url") or None
            self.last_feature_image_url = post.get("feature_image") or feature_image_url
            return post
        except (urllib.error.URLError, Exception):
            logger.warning("Failed to publish '%s' to Ghost API", title, exc_info=True)
            return None
