"""Backward-compat shim -- canonical locations: distill.intake.models + distill.intake.services."""

from distill.intake.models import FullTextResult  # noqa: F401
from distill.intake.services import (  # noqa: F401
    enrich_items,
    fetch_full_text,
)
