"""Knowledge graph domain — session data -> knowledge graph.

Public API re-exports for the graph domain.
"""

from distill.graph.context import ContextScorer
from distill.graph.extractor import (
    KNOWN_ENTITIES,
    PROJECT_ALIASES,
    SessionGraphExtractor,
)
from distill.graph.insights import (
    CouplingCluster,
    DailyInsights,
    ErrorHotspot,
    GraphInsights,
    RecurringProblem,
    ScopeWarning,
    format_insights_for_prompt,
)
from distill.graph.models import (
    ContextScore,
    EdgeType,
    GraphEdge,
    GraphNode,
    NodeType,
)
from distill.graph.prompts import get_context_prompt
from distill.graph.query import GraphQuery
from distill.graph.store import GRAPH_STORE_FILENAME, GraphStore
from distill.graph.synthesizer import (
    ContextSynthesisError,
    inject_context,
    synthesize_context,
)

__all__ = [
    # models
    "ContextScore",
    "EdgeType",
    "GraphEdge",
    "GraphNode",
    "NodeType",
    # store
    "GRAPH_STORE_FILENAME",
    "GraphStore",
    # extractor
    "KNOWN_ENTITIES",
    "PROJECT_ALIASES",
    "SessionGraphExtractor",
    # context scoring
    "ContextScorer",
    # query
    "GraphQuery",
    # insights
    "CouplingCluster",
    "DailyInsights",
    "ErrorHotspot",
    "GraphInsights",
    "RecurringProblem",
    "ScopeWarning",
    "format_insights_for_prompt",
    # prompts
    "get_context_prompt",
    # synthesizer
    "ContextSynthesisError",
    "inject_context",
    "synthesize_context",
]
