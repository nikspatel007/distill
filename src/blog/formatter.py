"""Backward-compatible re-export of ObsidianPublisher as BlogFormatter."""

from distill.blog.publishers.obsidian import ObsidianPublisher as BlogFormatter

__all__ = ["BlogFormatter"]
