"""Backward-compat shim -- canonical locations: models + services."""

from distill.blog.models import ThemeDefinition  # noqa: F401
from distill.blog.services import (  # noqa: F401
    _GENERIC_NAMES,
    THEMES,
    _entry_matches_theme,
    _is_generic_name,
    detect_series_candidates,
    gather_evidence,
    get_ready_themes,
    themes_from_seeds,
)
