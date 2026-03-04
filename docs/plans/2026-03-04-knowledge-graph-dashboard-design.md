# Knowledge Graph Dashboard — Design

**Date:** 2026-03-04
**Status:** Approved

## Goal

Surface the knowledge graph as an "activity story" dashboard page — showing what's on the user's mind, what they've been working on, and structural patterns in their codebase. Three tabs: Activity (narrative), Explorer (force-directed graph), Insights (pattern cards).

## Architecture

### Page Structure

**Route:** `/graph` — new TanStack Router page with three tabs sharing a time-window toggle.

**Time window:** `24h | 48h | 7d | 30d` pill selector, default `48h`. Shared across all tabs via URL search param or local state.

### Tab 1: Activity (default)

"What's on your mind" — chronological narrative of recent sessions.

**Top stats strip:** Session count, files touched, problems hit/resolved, top entities.

**Session timeline:** Vertical timeline, newest first. Each session card shows:
- Project name + timestamp + goal summary
- Files modified (chips), problems hit (red badges), entities (blue badges)
- Sessions connected by LEADS_TO edges shown as timeline connectors

**Data:** `GET /api/graph/activity?hours=48` → `gather_context_data()` + `daily_session_stats()`

### Tab 2: Explorer

Force-directed graph using `react-force-graph-2d` (Canvas-based, ~50KB).

- Nodes colored by type: sessions (blue), files (green), projects (purple), problems (red), entities (orange), goals (yellow)
- Edge thickness = weight
- Click node → side panel with details + neighbors + edges
- Search bar → highlights and centers on matching node
- Node size ∝ connection count
- Filter checkboxes to show/hide node types

**Data:** `GET /api/graph/nodes?hours=48` → filtered nodes + edges from GraphStore

### Tab 3: Insights

Pattern cards from `GraphInsights.generate_daily_insights()`:

1. **Scope Warnings** — sessions touching >5 files (high error correlation)
2. **Error Hotspots** — files most associated with problems
3. **Coupling Clusters** — file pairs that always change together
4. **Recurring Problems** — error patterns appearing across sessions

Each card: icon, count badge, expandable detail list.

**Data:** `GET /api/graph/insights?hours=48` → `generate_daily_insights(lookback_hours=...)`

## API Endpoints

| Endpoint | Returns | Python Source |
|----------|---------|---------------|
| `GET /api/graph/activity?hours=48` | Sessions with goals, files, problems, entities, stats | `gather_context_data()` + `daily_session_stats()` |
| `GET /api/graph/nodes?hours=48` | Nodes + edges for force graph | `GraphStore` filtered by time window |
| `GET /api/graph/about/:name` | Focus node + neighbors + edges | `GraphQuery.about()` |
| `GET /api/graph/insights?hours=48` | Coupling, hotspots, scope, recurring | `GraphInsights.generate_daily_insights()` |
| `GET /api/graph/stats` | Node/edge counts by type | `GraphQuery.stats()` |

All endpoints load `.distill-graph.json` from `OUTPUT_DIR` (same pattern as other routes).

## Python Bridge

The server (Bun/Hono) reads `.distill-graph.json` directly and runs the filtering/aggregation in TypeScript. The Python GraphQuery/GraphInsights classes are the reference implementation — the TS endpoints replicate the essential logic:

- **Activity:** Parse nodes by type, filter by time window, group sessions with their connected goals/files/problems/entities via edges.
- **Nodes:** Return raw nodes + edges filtered by time, let the frontend handle layout.
- **Insights:** Replicate the co-modification, hotspot, scope warning, and recurring problem algorithms in TS (they're all simple counting/grouping over edges and nodes — no LLM).
- **About:** BFS traversal from a focus node (already simple in the Python store).

Alternative: shell out to `uv run python -c "..."` for complex queries. But since the graph is just JSON and the algorithms are counting/grouping, pure TS is cleaner and faster.

## Zod Schemas

```typescript
// Node/Edge types
const NodeTypeEnum = z.enum(["session", "project", "file", "entity", "thread", "artifact", "goal", "problem", "decision", "insight"]);
const EdgeTypeEnum = z.enum(["modifies", "reads", "executes_in", "uses", "produces", "leads_to", "motivated_by", "blocked_by", "solved_by", "informed_by", "implements", "co_occurs", "part_of", "related_to", "references", "depends_on", "pivoted_from", "evolved_into"]);

// Graph data
const GraphNodeSchema = z.object({ ... });
const GraphEdgeSchema = z.object({ ... });

// Activity response
const GraphActivitySchema = z.object({
    sessions: z.array(...),
    top_entities: z.array(...),
    active_files: z.array(...),
    stats: z.object({ session_count, avg_files_per_session, total_problems })
});

// Insights response
const GraphInsightsSchema = z.object({
    coupling_clusters: z.array(...),
    error_hotspots: z.array(...),
    scope_warnings: z.array(...),
    recurring_problems: z.array(...)
});
```

## Dependencies

- `react-force-graph-2d` — Canvas-based force graph (~50KB, no heavy deps)

## Frontend Components

- `GraphPage` — tab container + time-window toggle
- `ActivityTab` — stats strip + session timeline cards
- `ExplorerTab` — force graph + search + node detail panel
- `InsightsTab` — pattern cards (scope, hotspots, coupling, recurring)

## Sidebar

Add to nav items in `Sidebar.tsx`:
- Icon: `Network` from lucide-react
- Label: "Graph"
- Route: `/graph`

## Files

| File | Change |
|------|--------|
| `web/shared/schemas.ts` | Add graph Zod schemas |
| `web/server/routes/graph.ts` | **New** — 5 API endpoints |
| `web/server/index.ts` | Register graph route |
| `web/src/routes/graph.tsx` | **New** — graph page with 3 tabs |
| `web/src/routeTree.gen.ts` | Add graph route |
| `web/src/components/layout/Sidebar.tsx` | Add Graph nav item |
| `package.json` | Add `react-force-graph-2d` |
