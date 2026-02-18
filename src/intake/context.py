"""Backward-compat shim -- canonical locations: distill.intake.models + distill.intake.services."""

from distill.intake.models import DailyIntakeContext  # noqa: F401
from distill.intake.services import (  # noqa: F401
    _render_content_section,
    _render_item,
    _render_seed_section,
    _render_session_section,
    prepare_daily_context,
)
