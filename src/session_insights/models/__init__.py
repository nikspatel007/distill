"""Session data models.

Re-exports unified models from parsers.models. The BaseSession class is the single
source of truth, accepting both parser fields (session_id, timestamp) and formatter
fields (id, start_time).
"""

from session_insights.models.insight import (
    Insight,
    InsightCollection,
    InsightSeverity,
    InsightType,
)
from session_insights.parsers.models import (
    BaseSession,
    ConversationTurn,
    SessionOutcome,
    ToolUsageSummary,
)

# Backward compatibility: formatter tests import ToolUsage from models
# This is the aggregated summary type (name, count), NOT the per-invocation ToolCall
ToolUsage = ToolUsageSummary

__all__ = [
    "BaseSession",
    "ConversationTurn",
    "Insight",
    "InsightCollection",
    "InsightSeverity",
    "InsightType",
    "SessionOutcome",
    "ToolUsage",
    "ToolUsageSummary",
]
