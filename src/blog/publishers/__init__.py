"""Blog publisher factory and registry."""

from __future__ import annotations

from distill.blog.config import GhostConfig, Platform
from distill.blog.publishers.base import BlogPublisher
from distill.blog.synthesizer import BlogSynthesizer


def create_publisher(
    platform: Platform | str,
    *,
    synthesizer: BlogSynthesizer | None = None,
    ghost_config: GhostConfig | None = None,
    postiz_config: object | None = None,
    skip_api: bool = False,
) -> BlogPublisher:
    """Create a publisher for the given platform.

    Args:
        platform: The target platform.
        synthesizer: Required for social publishers that need LLM re-synthesis.
        ghost_config: Optional Ghost CMS configuration for live publishing.
        postiz_config: Optional PostizConfig for scheduling and API settings.
        skip_api: If True, publishers format content but skip external API calls.
            Content is saved locally and to ContentStore for later publishing
            via the Studio UI.

    Returns:
        A BlogPublisher instance for the platform.

    Raises:
        ValueError: If the platform is unknown.
    """
    if isinstance(platform, str):
        platform = Platform(platform)

    from distill.blog.publishers.ghost import GhostPublisher
    from distill.blog.publishers.markdown import MarkdownPublisher
    from distill.blog.publishers.obsidian import ObsidianPublisher
    from distill.blog.publishers.postiz import PostizBlogPublisher

    publishers: dict[Platform, BlogPublisher] = {
        Platform.OBSIDIAN: ObsidianPublisher(),
        Platform.GHOST: GhostPublisher(ghost_config=ghost_config, skip_api=skip_api),
        Platform.MARKDOWN: MarkdownPublisher(),
        Platform.POSTIZ: PostizBlogPublisher(
            synthesizer=synthesizer, postiz_config=postiz_config, skip_api=skip_api
        ),
    }

    if platform in publishers:
        return publishers[platform]

    raise ValueError(f"Unknown platform: {platform!r}")
