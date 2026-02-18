"""Backward-compat shim -- canonical locations: models + services."""

from distill.blog.models import BlogPostRecord, BlogState  # noqa: F401
from distill.blog.services import (  # noqa: F401
    STATE_FILENAME,
    load_blog_state,
    save_blog_state,
)
