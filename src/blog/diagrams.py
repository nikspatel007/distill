"""Backward-compat shim -- canonical location: distill.blog.services."""

from distill.blog.services import (  # noqa: F401
    VALID_DIAGRAM_TYPES,
    clean_diagrams,
    extract_mermaid_blocks,
    validate_mermaid,
)
