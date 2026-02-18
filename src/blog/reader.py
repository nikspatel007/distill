"""Backward-compat shim -- canonical locations: models + services."""

from distill.blog.models import IntakeDigestEntry, JournalEntry  # noqa: F401
from distill.blog.services import (  # noqa: F401
    JournalReader,
    _extract_prose,
    _parse_frontmatter,
)
