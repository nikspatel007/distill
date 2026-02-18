"""Backward-compat shim -- canonical locations: models + services."""

from distill.blog.models import ThematicBlogContext, WeeklyBlogContext  # noqa: F401
from distill.blog.services import prepare_thematic_context, prepare_weekly_context  # noqa: F401
