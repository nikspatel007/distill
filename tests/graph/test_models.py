"""Tests for knowledge graph Pydantic models."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from distill.graph.models import (
    ContextScore,
    EdgeType,
    GraphEdge,
    GraphNode,
    NodeType,
)

# -- NodeType enum -----------------------------------------------------------


class TestNodeType:
    def test_all_values(self):
        expected = {
            "session",
            "project",
            "file",
            "entity",
            "thread",
            "artifact",
            "goal",
            "problem",
            "decision",
            "insight",
        }
        assert {v.value for v in NodeType} == expected

    def test_is_str(self):
        assert isinstance(NodeType.SESSION, str)
        assert NodeType.SESSION == "session"

    def test_from_string(self):
        assert NodeType("project") == NodeType.PROJECT
        assert NodeType("insight") == NodeType.INSIGHT


# -- EdgeType enum -----------------------------------------------------------


class TestEdgeType:
    def test_all_values(self):
        expected = {
            "modifies",
            "reads",
            "executes_in",
            "uses",
            "produces",
            "leads_to",
            "motivated_by",
            "blocked_by",
            "solved_by",
            "informed_by",
            "implements",
            "co_occurs",
            "part_of",
            "related_to",
            "references",
            "depends_on",
            "pivoted_from",
            "evolved_into",
        }
        assert {v.value for v in EdgeType} == expected

    def test_is_str(self):
        assert isinstance(EdgeType.MODIFIES, str)
        assert EdgeType.MODIFIES == "modifies"

    def test_from_string(self):
        assert EdgeType("uses") == EdgeType.USES
        assert EdgeType("blocked_by") == EdgeType.BLOCKED_BY


# -- GraphNode ---------------------------------------------------------------


class TestGraphNode:
    def test_minimal_creation(self):
        node = GraphNode(node_type=NodeType.SESSION, name="session-001")
        assert node.node_type == NodeType.SESSION
        assert node.name == "session-001"
        assert isinstance(node.id, UUID)
        assert node.properties == {}
        assert node.embedding == []
        assert node.source_id == ""
        assert node.first_seen is not None
        assert node.last_seen is not None

    def test_with_properties(self):
        props = {"language": "python", "lines": 42}
        node = GraphNode(
            node_type=NodeType.FILE,
            name="src/main.py",
            properties=props,
            source_id="abc-123",
        )
        assert node.properties == props
        assert node.source_id == "abc-123"

    def test_with_embedding(self):
        emb = [0.1, 0.2, 0.3]
        node = GraphNode(
            node_type=NodeType.ENTITY,
            name="Python",
            embedding=emb,
        )
        assert node.embedding == [0.1, 0.2, 0.3]

    def test_node_key_property(self):
        node = GraphNode(node_type=NodeType.PROJECT, name="distill")
        assert node.node_key == "project:distill"

    def test_node_key_various_types(self):
        cases = [
            (NodeType.GOAL, "ship-v1", "goal:ship-v1"),
            (NodeType.PROBLEM, "slow-build", "problem:slow-build"),
            (NodeType.DECISION, "use-pydantic", "decision:use-pydantic"),
        ]
        for ntype, name, expected_key in cases:
            node = GraphNode(node_type=ntype, name=name)
            assert node.node_key == expected_key

    def test_custom_timestamps(self):
        ts = datetime(2026, 2, 14, 10, 0, 0)
        node = GraphNode(
            node_type=NodeType.ARTIFACT,
            name="report.pdf",
            first_seen=ts,
            last_seen=ts,
        )
        assert node.first_seen == ts
        assert node.last_seen == ts

    def test_serialization_roundtrip(self):
        node = GraphNode(
            node_type=NodeType.THREAD,
            name="refactor-thread",
            properties={"status": "active"},
        )
        data = node.model_dump()
        assert data["node_type"] == "thread"
        assert data["name"] == "refactor-thread"
        restored = GraphNode.model_validate(data)
        assert restored.node_type == NodeType.THREAD
        assert restored.name == "refactor-thread"
        assert restored.id == node.id


# -- GraphEdge ---------------------------------------------------------------


class TestGraphEdge:
    def test_minimal_creation(self):
        edge = GraphEdge(
            source_key="session:s1",
            target_key="file:main.py",
            edge_type=EdgeType.MODIFIES,
        )
        assert isinstance(edge.id, UUID)
        assert edge.source_key == "session:s1"
        assert edge.target_key == "file:main.py"
        assert edge.edge_type == EdgeType.MODIFIES
        assert edge.weight == 1.0
        assert edge.properties == {}
        assert edge.created_at is not None

    def test_custom_weight(self):
        edge = GraphEdge(
            source_key="entity:Python",
            target_key="project:distill",
            edge_type=EdgeType.USES,
            weight=0.8,
        )
        assert edge.weight == 0.8

    def test_with_properties(self):
        edge = GraphEdge(
            source_key="problem:slow",
            target_key="decision:cache",
            edge_type=EdgeType.SOLVED_BY,
            properties={"confidence": 0.95},
        )
        assert edge.properties["confidence"] == 0.95

    def test_edge_key_property(self):
        edge = GraphEdge(
            source_key="session:s1",
            target_key="file:main.py",
            edge_type=EdgeType.MODIFIES,
        )
        assert edge.edge_key == "session:s1->file:main.py:modifies"

    def test_edge_key_various_types(self):
        cases = [
            ("goal:ship", "problem:bug", EdgeType.BLOCKED_BY, "goal:ship->problem:bug:blocked_by"),
            ("insight:a", "decision:b", EdgeType.INFORMED_BY, "insight:a->decision:b:informed_by"),
        ]
        for src, tgt, etype, expected_key in cases:
            edge = GraphEdge(source_key=src, target_key=tgt, edge_type=etype)
            assert edge.edge_key == expected_key

    def test_serialization_roundtrip(self):
        edge = GraphEdge(
            source_key="entity:Rust",
            target_key="entity:Python",
            edge_type=EdgeType.RELATED_TO,
            weight=0.5,
        )
        data = edge.model_dump()
        assert data["edge_type"] == "related_to"
        assert data["weight"] == 0.5
        restored = GraphEdge.model_validate(data)
        assert restored.edge_type == EdgeType.RELATED_TO
        assert restored.id == edge.id


# -- ContextScore -------------------------------------------------------------


class TestContextScore:
    def test_basic_creation(self):
        score = ContextScore(
            node_key="entity:Python",
            score=0.85,
            components={"recency": 0.9, "frequency": 0.8},
        )
        assert score.node_key == "entity:Python"
        assert score.focus_key is None
        assert score.score == 0.85
        assert score.components == {"recency": 0.9, "frequency": 0.8}
        assert score.computed_at is not None

    def test_with_focus_key(self):
        score = ContextScore(
            node_key="file:main.py",
            focus_key="project:distill",
            score=0.72,
            components={"proximity": 0.7},
        )
        assert score.focus_key == "project:distill"

    def test_without_focus_key(self):
        score = ContextScore(
            node_key="thread:refactor",
            score=0.5,
            components={},
        )
        assert score.focus_key is None

    def test_serialization_roundtrip(self):
        ts = datetime(2026, 2, 14, 12, 0, 0)
        score = ContextScore(
            node_key="goal:ship",
            focus_key="project:app",
            score=0.99,
            components={"importance": 1.0},
            computed_at=ts,
        )
        data = score.model_dump()
        assert data["focus_key"] == "project:app"
        restored = ContextScore.model_validate(data)
        assert restored.score == 0.99
        assert restored.computed_at == ts
