"""Ghost CMS integration — config and API client.

Shared by both blog and intake publishers so that neither layer
depends on the other.
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class GhostConfig(BaseModel):
    """Configuration for Ghost CMS publishing."""

    url: str = ""
    admin_api_key: str = ""
    newsletter_slug: str = ""
    auto_publish: bool = True
    blog_as_draft: bool = False

    @property
    def is_configured(self) -> bool:
        return bool(self.url and self.admin_api_key)

    @classmethod
    def from_env(cls) -> GhostConfig:
        """Create config from environment variables."""
        return cls(
            url=os.environ.get("GHOST_URL", ""),
            admin_api_key=os.environ.get("GHOST_ADMIN_API_KEY", ""),
            newsletter_slug=os.environ.get("GHOST_NEWSLETTER_SLUG", ""),
        )


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
