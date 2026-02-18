"""Backward-compat shim -- canonical location: distill.blog.services."""

from distill.blog.services import (  # noqa: F401
    BlogSynthesisError,
    BlogSynthesizer,
    _render_thematic_prompt,
    _render_weekly_prompt,
    _strip_json_fences,
    _strip_preamble,
)
