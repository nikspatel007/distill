"""Pipeline modules — orchestration layer for the distill content pipeline.

Each sub-module handles one stage of the distill pipeline:
  journal  — session -> daily journal entries
  blog     — journal entries -> blog posts (weekly, thematic, reading-list)
  intake   — external content -> daily digests
  social   — journal -> daily social posts

Pipeline modules import domain logic via public APIs:
  - ``from distill.blog import ...`` (not ``distill.blog.services``)
  - ``from distill.journal import ...`` (not ``distill.journal.models``)
  - ``from distill.intake import ...`` (not ``distill.intake.config``)
  - ``from distill.memory import ...``
  - ``from distill.shared.* import ...`` for config, editorial, images, etc.
  - Sub-package ``__init__`` imports (``distill.blog.publishers``,
    ``distill.intake.parsers``) are fine.

All public symbols are re-exported from distill.core for backward compat.
"""
