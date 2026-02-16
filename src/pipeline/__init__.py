"""Pipeline modules — extracted from core.py for maintainability.

Each sub-module handles one stage of the distill pipeline:
  journal  — session → daily journal entries
  blog     — journal entries → blog posts (weekly, thematic, reading-list)
  intake   — external content → daily digests
  social   — journal → daily social posts

All public symbols are re-exported from distill.core for backward compat.
Import directly from sub-modules to avoid circular imports.
"""
