"""Backward-compat shim -- canonical locations: distill.intake.models + distill.intake.services."""

from distill.intake.models import TopicCluster  # noqa: F401

# Re-export private names that tests/other code may reference
from distill.intake.services import _CLUSTER_STOPWORDS as _STOPWORDS  # noqa: F401
from distill.intake.services import _CLUSTER_STRIP_TABLE as _STRIP_TABLE  # noqa: F401
from distill.intake.services import (  # noqa: F401
    _build_tfidf,
    _cosine_similarity,
    _item_text,
    _make_label,
    _merge_vectors,
    _top_keywords,
    cluster_items,
    render_clustered_context,
)
from distill.intake.services import _tokenize_cluster as _tokenize  # noqa: F401
