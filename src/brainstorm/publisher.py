"""Backward-compat shim -- re-exports publisher logic from services."""
from distill.brainstorm.services import (  # noqa: F401
    _render_markdown,
    publish_calendar,
)
