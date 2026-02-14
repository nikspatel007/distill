"""Core Pydantic models for the knowledge graph."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class NodeType(StrEnum):
    """Types of nodes in the knowledge graph."""

    SESSION = "session"
    PROJECT = "project"
    FILE = "file"
    ENTITY = "entity"
    THREAD = "thread"
    ARTIFACT = "artifact"
    GOAL = "goal"
    PROBLEM = "problem"
    DECISION = "decision"
    INSIGHT = "insight"


class EdgeType(StrEnum):
    """Types of edges (relationships) in the knowledge graph."""

    MODIFIES = "modifies"
    READS = "reads"
    EXECUTES_IN = "executes_in"
    USES = "uses"
    PRODUCES = "produces"
    LEADS_TO = "leads_to"
    MOTIVATED_BY = "motivated_by"
    BLOCKED_BY = "blocked_by"
    SOLVED_BY = "solved_by"
    INFORMED_BY = "informed_by"
    IMPLEMENTS = "implements"
    CO_OCCURS = "co_occurs"
    PART_OF = "part_of"
    RELATED_TO = "related_to"
    REFERENCES = "references"
    DEPENDS_ON = "depends_on"
    PIVOTED_FROM = "pivoted_from"
    EVOLVED_INTO = "evolved_into"


class GraphNode(BaseModel):
    """A node in the knowledge graph."""

    id: UUID = Field(default_factory=uuid4)
    node_type: NodeType
    name: str
    properties: dict[str, object] = Field(default_factory=dict)
    embedding: list[float] = Field(default_factory=list)
    first_seen: datetime = Field(default_factory=datetime.now)
    last_seen: datetime = Field(default_factory=datetime.now)
    source_id: str = ""

    @property
    def node_key(self) -> str:
        """Canonical key: ``node_type:name``."""
        return f"{self.node_type}:{self.name}"


class GraphEdge(BaseModel):
    """A directed edge in the knowledge graph."""

    id: UUID = Field(default_factory=uuid4)
    source_key: str
    target_key: str
    edge_type: EdgeType
    weight: float = 1.0
    properties: dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)

    @property
    def edge_key(self) -> str:
        """Canonical key: ``source_key->target_key:edge_type``."""
        return f"{self.source_key}->{self.target_key}:{self.edge_type}"


class ContextScore(BaseModel):
    """Relevance score for a node within a focus context."""

    node_key: str
    focus_key: str | None = None
    score: float
    components: dict[str, float] = Field(default_factory=dict)
    computed_at: datetime = Field(default_factory=datetime.now)
