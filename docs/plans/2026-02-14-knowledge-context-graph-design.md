# Knowledge Graph + Context Graph Design

**Date:** 2026-02-14
**Status:** Approved
**Scope:** Transform raw Claude Code session logs into a two-layer graph system

## Problem

Distill has ~13 GB of raw session data across 5,260+ project directories. This data contains rich relational information (entities, decisions, causal chains, file dependencies) but it's stored as flat JSONL transcripts. The existing pipeline extracts summaries and themes but discards structural and causal relationships.

We want to:
1. Convert raw logs into a queryable knowledge representation
2. Group work by logical narrative arcs, not just directory paths
3. Link sessions, files, decisions, and entities across projects
4. Surface what's relevant RIGHT NOW for both humans (dashboard) and machines (Claude sessions)

## Architecture: Two Layers

### Layer 1: Knowledge Graph (static facts)

Durable, append-mostly store of everything that happened and why.

### Layer 2: Context Graph (dynamic relevance)

Live query layer that scores "what matters right now" based on temporal, structural, and semantic relevance.

---

## Knowledge Graph

### Node Types (10 total)

#### Structural nodes (what happened)

| Node Type | Represents | Source |
|---|---|---|
| `session` | A single Claude Code conversation | JSONL transcript |
| `project` | A codebase/repo | `cwd` from sessions |
| `file` | A source file touched during work | Tool calls (Edit, Write, Read) |
| `entity` | Technology, person, concept, or org | LLM extraction + heuristics |
| `thread` | Multi-session narrative arc | Graph community detection |
| `artifact` | Produced output (blog post, journal) | Pipeline output tracking |

#### Intent nodes (why it happened)

| Node Type | Represents | Source |
|---|---|---|
| `goal` | What the user was trying to accomplish | First user message + LLM intent extraction |
| `problem` | Bug, blocker, or issue encountered | Error messages, debugging sequences |
| `decision` | Architectural or design choice | LLM extraction from assistant reasoning |
| `insight` | A realization that changed direction | Assistant reasoning patterns |

### PostgreSQL Schema: Nodes

```sql
CREATE TABLE graph_nodes (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    node_type   TEXT NOT NULL,
    name        TEXT NOT NULL,
    properties  JSONB DEFAULT '{}',
    embedding   vector(384),
    first_seen  TIMESTAMPTZ NOT NULL,
    last_seen   TIMESTAMPTZ NOT NULL,
    source_id   TEXT,
    UNIQUE(node_type, name)
);
CREATE INDEX idx_nodes_type ON graph_nodes(node_type);
CREATE INDEX idx_nodes_name ON graph_nodes USING gin(name gin_trgm_ops);
CREATE INDEX idx_nodes_embedding ON graph_nodes USING ivfflat(embedding vector_cosine_ops);
```

`UNIQUE(node_type, name)` ensures automatic deduplication.

`properties` JSONB holds type-specific metadata:
- Session: `{model, branch, duration_minutes, tool_count, token_usage}`
- File: `{language, last_modified, line_count}`
- Decision: `{rationale, alternatives_considered, confidence}`
- Entity: `{entity_subtype, description, url}`
- Problem: `{error_message, stack_trace, severity}`
- Goal: `{intent_text, scope, status}`

### Edge Types (13 total)

#### Work edges (what happened)

| Edge Type | From -> To | Meaning |
|---|---|---|
| `modifies` | session -> file | Session changed this file |
| `reads` | session -> file | Session read this file |
| `executes_in` | session -> project | Session ran in this project |
| `uses` | session -> entity | Session used this technology |
| `produces` | session -> artifact | Session led to this output |

#### Causal edges (why things connect)

| Edge Type | From -> To | Meaning |
|---|---|---|
| `leads_to` | session -> session | Work continued in another session |
| `motivated_by` | session -> goal | Why this session started |
| `blocked_by` | session -> problem | Why work stalled |
| `solved_by` | problem -> session | Why this fix worked |
| `informed_by` | decision -> insight | Why this decision was made |
| `implements` | session -> decision | Session implemented a prior decision |

#### Semantic edges (how things relate)

| Edge Type | From -> To | Meaning |
|---|---|---|
| `co_occurs` | entity -> entity | Entities appear together frequently |
| `part_of` | session -> thread | Session belongs to narrative arc |
| `related_to` | entity -> entity | Semantic relationship |
| `references` | artifact -> session | Blog post draws from sessions |
| `depends_on` | file -> file | File imports/requires another |
| `pivoted_from` | goal -> goal | Direction changed |
| `evolved_into` | thread -> thread | Work stream transformed |

### PostgreSQL Schema: Edges

```sql
CREATE TABLE graph_edges (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id   UUID NOT NULL REFERENCES graph_nodes(id) ON DELETE CASCADE,
    target_id   UUID NOT NULL REFERENCES graph_nodes(id) ON DELETE CASCADE,
    edge_type   TEXT NOT NULL,
    weight      REAL DEFAULT 1.0,
    properties  JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE(source_id, target_id, edge_type)
);
CREATE INDEX idx_edges_source ON graph_edges(source_id);
CREATE INDEX idx_edges_target ON graph_edges(target_id);
CREATE INDEX idx_edges_type ON graph_edges(edge_type);
```

Weight semantics:
- `modifies`: number of edits to file in session
- `co_occurs`: frequency of co-occurrence (normalized 0-1)
- `leads_to`: confidence based on temporal proximity + content overlap
- `reads`: number of read operations

Edge properties examples:
- `modifies`: `{lines_added: 45, lines_removed: 12}`
- `leads_to`: `{gap_hours: 2.5, shared_files: ["src/store.py"], branch: "feat/graph"}`
- `solved_by`: `{root_cause: "SQLite file locked during read"}`

### Causal Chain Example

```
goal: "Add content ingestion to distill"
  |-- motivated_by <-- session: "Research RSS parsing options"
  |     \-- insight: "feedparser handles OPML natively"
  |           \-- informed_by --> decision: "Use feedparser, not raw XML"
  |-- motivated_by <-- session: "Build RSS parser"
  |     |-- blocked_by --> problem: "SQLite browser history locked"
  |     |     \-- solved_by --> session: "Copy SQLite to temp before reading"
  |     \-- produces --> file: src/intake/parsers/rss.py
  |-- motivated_by <-- session: "Add browser history parser"
  |     \-- informed_by --> insight: "Chrome and Safari use different schemas"
  \-- evolved_into --> goal: "Build unified intake pipeline with 8 sources"
```

### Graph Traversal via Recursive CTEs

```sql
-- Everything 2 hops from a thread node
WITH RECURSIVE reachable AS (
    SELECT target_id AS node_id, 1 AS depth
    FROM graph_edges WHERE source_id = :thread_node_id
    UNION
    SELECT e.target_id, r.depth + 1
    FROM graph_edges e JOIN reachable r ON e.source_id = r.node_id
    WHERE r.depth < 2
)
SELECT n.* FROM graph_nodes n JOIN reachable r ON n.id = r.node_id;
```

---

## Context Graph

### Problem

Knowledge Graph grows without bound. Context Graph answers: "Given what I'm doing right now, what from the Knowledge Graph is relevant?"

### Three Dimensions of Relevance

**Temporal:** How recently was this node active?
```
relevance_temporal(node) = e^(-lambda * days_since_last_seen)
```
Nodes decay independently. A thread spanning months stays warm because `last_seen` keeps updating.

**Structural:** How close in the graph to the current focus?
```
relevance_structural(node, focus) = 1 / (1 + shortest_path(node, focus))
```

**Semantic:** How topically similar to the current focus?
```
relevance_semantic(node, focus) = cosine_similarity(node.embedding, focus.embedding)
```

### Combined Score

```
relevance(node, focus, now) =
    0.3 * temporal(node, now) +
    0.5 * structural(node, focus) +
    0.2 * semantic(node, focus)
```

Structural distance matters most. Recency second. Semantic as catch-all.

### PostgreSQL Schema: Context

```sql
CREATE TABLE context_scores (
    node_id       UUID REFERENCES graph_nodes(id) ON DELETE CASCADE,
    focus_id      UUID REFERENCES graph_nodes(id),  -- NULL = global context
    score         REAL NOT NULL,
    components    JSONB DEFAULT '{}',
    computed_at   TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY(node_id, focus_id)
);

CREATE MATERIALIZED VIEW active_context AS
SELECT n.*, cs.score, cs.components
FROM graph_nodes n
JOIN context_scores cs ON n.id = cs.node_id
WHERE cs.focus_id IS NULL AND cs.score > 0.3
ORDER BY cs.score DESC;
```

### Refresh Strategy

- On session start: compute for current project/branch focus
- On explicit dashboard query
- Nightly batch for global `active_context` materialized view
- Cached in `context_scores`, invalidated when new edges touch a node

### Consumer Output

**For Claude sessions:**
```
ACTIVE CONTEXT:
- Thread: "Building knowledge graph for distill" (5 sessions, 2 days)
  - Open decision: Storage backend (resolved: pgvector)
  - Active goal: Design context graph layer
  - Key insight: JSONL uuid/parentUuid chains are unused execution DAGs
- Related: "Intake pipeline" thread (last active 1 week ago)
  - Decision: Use feedparser for RSS (implemented)
  - 3 unresolved problems flagged
- Hot files: src/store.py (8 modifications), src/memory.py (5)
```

**For dashboard:** Timeline grouped by thread, entity neighborhood map, decisions log with rationale chains, node opacity mapped to relevance score.

---

## Extraction Pipeline

### Tier 1: Heuristic (free, instant)

| What | How | Produces |
|---|---|---|
| Session node | One per JSONL file, name = first user message | `session` node |
| Project node | `cwd` basename | `project` node + `executes_in` edge |
| File nodes | Tool call args (Edit/Write/Read/Grep/Glob) | `file` nodes + `modifies`/`reads` edges |
| File deps | Regex: `from X import Y`, `import X` | `depends_on` edges |
| Goal (rough) | First user message | `goal` node + `motivated_by` edge |
| Session chains | Same project + branch + <4 hour gap | `leads_to` edges |
| Token usage | `usage` field in assistant entries | Properties on session node |

### Tier 2: Pattern-matched (free, medium accuracy)

| What | How | Produces |
|---|---|---|
| Problems | Non-zero Bash exits + surrounding context | `problem` + `blocked_by` edges |
| Entity hints | Curated tech name list | `entity` + `uses` edges |
| Debug detection | Same file Read-Edit-Bash 3+ times | Session property annotation |

### Tier 3: LLM extraction (Haiku, batched, incremental)

| What | Produces |
|---|---|
| Decision extraction | `decision` + `insight` nodes, `informed_by`/`resolves` edges |
| Goal refinement | Refined `goal` name + `rationale` property |
| Thread detection | `thread` nodes + `part_of` edges |
| Entity relationships | `co_occurs`/`related_to` edges with context |

### Pipeline Flow

```
JSONL file (new or backfill)
  -> Tier 1 (heuristic, instant)
  -> Tier 2 (pattern match, instant)
  -> Queue for Tier 3 (LLM, async batch)
  -> Update context_scores for affected nodes
```

### Cost Management

- Haiku for all LLM extraction (cheap, fast)
- Incremental: only process new sessions
- Tiered: heuristics first, LLM only for gaps
- Cached: extraction results stored in node/edge properties

---

## Module Structure

```
src/graph/
    __init__.py
    models.py       # GraphNode, GraphEdge, ContextScore (Pydantic)
    extractor.py    # Tier 1-2 heuristic extraction
    intelligence.py # Tier 3 LLM extraction
    store.py        # PostgreSQL graph tables
    context.py      # Context scoring and subgraph queries
    query.py        # High-level query API for dashboard + Claude
```

### Integration with Existing Pipeline

```
Sessions -> Parsers -> [existing] Analyzers/Journal/Blog
                    \-> [NEW] GraphExtractor -> graph_nodes/graph_edges
                                             -> context_scores refresh
```

### CLI

```bash
distill graph --build          # Backfill from ~/.claude/projects/
distill graph --query "intake" # Query the graph
distill graph --stats          # Node/edge counts, top entities
```

### Backfill Strategy

Iterate `~/.claude/projects/*/` chronologically:
- Tier 1-2 on everything (fast, free)
- Tier 3 on last 30 days only (unless explicitly requested)
- Older sessions get structural edges only
