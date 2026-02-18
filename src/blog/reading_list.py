"""Backward-compat shim -- canonical locations: models + services."""

from distill.blog.models import ReadingListContext  # noqa: F401
from distill.blog.services import (  # noqa: F401
    prepare_reading_list_context,
    render_reading_list_prompt,
)
