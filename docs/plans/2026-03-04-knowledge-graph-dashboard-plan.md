# Knowledge Graph Dashboard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a `/graph` page to the web dashboard with three tabs — Activity (narrative timeline), Explorer (force-directed graph), and Insights (pattern cards) — powered by the existing knowledge graph in `.distill-graph.json`.

**Architecture:** The Hono server reads `.distill-graph.json` directly and computes activity, node/edge filtering, and insight aggregation in TypeScript (no Python subprocess). The frontend uses `react-force-graph-2d` for the explorer tab. All data flows through Zod-validated API responses.

**Tech Stack:** Hono API routes, Zod schemas, React + TanStack Router, `react-force-graph-2d`, Tailwind CSS, Bun test runner.

---

### Task 1: Zod Schemas for Graph Data

**Files:**
- Modify: `web/shared/schemas.ts`

**Step 1: Add graph schemas to schemas.ts**

Add after the Shares section (before Studio section), following the existing pattern:

```typescript
// --- Knowledge Graph ---

export const NodeTypeEnum = z.enum([
	"session", "project", "file", "entity", "thread",
	"artifact", "goal", "problem", "decision", "insight",
]);

export const EdgeTypeEnum = z.enum([
	"modifies", "reads", "executes_in", "uses", "produces",
	"leads_to", "motivated_by", "blocked_by", "solved_by",
	"informed_by", "implements", "co_occurs", "part_of",
	"related_to", "references", "depends_on", "pivoted_from",
	"evolved_into",
]);

export const GraphNodeSchema = z.object({
	id: z.string(),
	node_type: NodeTypeEnum,
	name: z.string(),
	properties: z.record(z.unknown()).default({}),
	first_seen: z.string(),
	last_seen: z.string(),
});

export const GraphEdgeSchema = z.object({
	id: z.string(),
	source_key: z.string(),
	target_key: z.string(),
	edge_type: EdgeTypeEnum,
	weight: z.number().default(1),
	properties: z.record(z.unknown()).default({}),
});

export const GraphSessionSchema = z.object({
	id: z.string(),
	summary: z.string(),
	hours_ago: z.number(),
	project: z.string(),
	goal: z.string(),
	files_modified: z.array(z.string()),
	files_read: z.array(z.string()),
	problems: z.array(z.object({
		error: z.string(),
		command: z.string(),
		resolved: z.boolean(),
	})),
	entities: z.array(z.string()),
});

export const GraphActivityResponseSchema = z.object({
	project: z.string(),
	time_window_hours: z.number(),
	sessions: z.array(GraphSessionSchema),
	top_entities: z.array(z.object({ name: z.string(), count: z.number() })),
	active_files: z.array(z.object({ path: z.string(), hours_ago: z.number() })),
	stats: z.object({
		session_count: z.number(),
		avg_files_per_session: z.number(),
		total_problems: z.number(),
	}),
});

export const GraphNodesResponseSchema = z.object({
	nodes: z.array(GraphNodeSchema),
	edges: z.array(GraphEdgeSchema),
});

export const CouplingClusterSchema = z.object({
	files: z.array(z.string()),
	co_modification_count: z.number(),
	description: z.string().default(""),
});

export const ErrorHotspotSchema = z.object({
	file: z.string(),
	problem_count: z.number(),
	recent_problems: z.array(z.string()),
});

export const ScopeWarningSchema = z.object({
	session_name: z.string(),
	files_modified: z.number(),
	project: z.string().default(""),
	problems_hit: z.number().default(0),
});

export const RecurringProblemSchema = z.object({
	pattern: z.string(),
	occurrence_count: z.number(),
	sessions: z.array(z.string()),
});

export const GraphInsightsResponseSchema = z.object({
	date: z.string(),
	coupling_clusters: z.array(CouplingClusterSchema),
	error_hotspots: z.array(ErrorHotspotSchema),
	scope_warnings: z.array(ScopeWarningSchema),
	recurring_problems: z.array(RecurringProblemSchema),
	session_count: z.number(),
	avg_files_per_session: z.number(),
	total_problems: z.number(),
});

export const GraphAboutResponseSchema = z.object({
	focus: z.object({
		name: z.string(),
		type: z.string(),
		summary: z.string(),
	}).nullable(),
	neighbors: z.array(z.object({
		name: z.string(),
		type: z.string(),
		relevance: z.number(),
		last_seen: z.string(),
	})),
	edges: z.array(z.object({
		type: z.string(),
		source: z.string(),
		target: z.string(),
		weight: z.number(),
	})),
});

export const GraphStatsResponseSchema = z.object({
	total_nodes: z.number(),
	total_edges: z.number(),
	nodes_by_type: z.record(z.string(), z.number()),
	edges_by_type: z.record(z.string(), z.number()),
});
```

**Step 2: Add type exports at the bottom of schemas.ts**

```typescript
export type GraphNode = z.infer<typeof GraphNodeSchema>;
export type GraphEdge = z.infer<typeof GraphEdgeSchema>;
export type GraphSession = z.infer<typeof GraphSessionSchema>;
export type GraphActivityResponse = z.infer<typeof GraphActivityResponseSchema>;
export type GraphNodesResponse = z.infer<typeof GraphNodesResponseSchema>;
export type GraphInsightsResponse = z.infer<typeof GraphInsightsResponseSchema>;
export type GraphAboutResponse = z.infer<typeof GraphAboutResponseSchema>;
export type GraphStatsResponse = z.infer<typeof GraphStatsResponseSchema>;
export type CouplingCluster = z.infer<typeof CouplingClusterSchema>;
export type ErrorHotspot = z.infer<typeof ErrorHotspotSchema>;
export type ScopeWarning = z.infer<typeof ScopeWarningSchema>;
export type RecurringProblem = z.infer<typeof RecurringProblemSchema>;
```

**Step 3: Verify TypeScript compiles**

Run: `cd web && npx tsc --noEmit`
Expected: 0 errors

**Step 4: Commit**

```bash
git add web/shared/schemas.ts
git commit -m "feat(graph): add Zod schemas for knowledge graph API"
```

---

### Task 2: Graph API Route — Loading + Stats + About

**Files:**
- Create: `web/server/routes/graph.ts`
- Modify: `web/server/index.ts`

**Step 1: Write graph.ts with load helper, stats, and about endpoints**

Create `web/server/routes/graph.ts`:

```typescript
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { Hono } from "hono";
import { z } from "zod";
import { GraphNodeSchema, GraphEdgeSchema } from "../../shared/schemas.js";
import { getConfig } from "../lib/config.js";

const app = new Hono();
const GRAPH_FILE = ".distill-graph.json";

interface RawNode {
	id: string;
	node_type: string;
	name: string;
	properties: Record<string, unknown>;
	embedding?: number[];
	first_seen: string;
	last_seen: string;
	source_id?: string;
}

interface RawEdge {
	id: string;
	source_key: string;
	target_key: string;
	edge_type: string;
	weight: number;
	properties: Record<string, unknown>;
	created_at: string;
}

interface GraphData {
	nodes: RawNode[];
	edges: RawEdge[];
}

async function loadGraph(outputDir: string): Promise<GraphData> {
	try {
		const raw = await readFile(join(outputDir, GRAPH_FILE), "utf-8");
		const data = JSON.parse(raw);
		return {
			nodes: Array.isArray(data.nodes) ? data.nodes : [],
			edges: Array.isArray(data.edges) ? data.edges : [],
		};
	} catch {
		return { nodes: [], edges: [] };
	}
}

function nodeKey(node: RawNode): string {
	return `${node.node_type}:${node.name}`;
}

function hoursAgo(isoDate: string, now: Date): number {
	const d = new Date(isoDate);
	return (now.getTime() - d.getTime()) / (1000 * 60 * 60);
}

// GET /api/graph/stats
app.get("/api/graph/stats", async (c) => {
	const { OUTPUT_DIR } = getConfig();
	const graph = await loadGraph(OUTPUT_DIR);

	const nodesByType: Record<string, number> = {};
	for (const n of graph.nodes) {
		nodesByType[n.node_type] = (nodesByType[n.node_type] ?? 0) + 1;
	}

	const edgesByType: Record<string, number> = {};
	for (const e of graph.edges) {
		edgesByType[e.edge_type] = (edgesByType[e.edge_type] ?? 0) + 1;
	}

	return c.json({
		total_nodes: graph.nodes.length,
		total_edges: graph.edges.length,
		nodes_by_type: nodesByType,
		edges_by_type: edgesByType,
	});
});

// GET /api/graph/about/:name — focus node + neighbors + edges
app.get("/api/graph/about/:name", async (c) => {
	const name = decodeURIComponent(c.req.param("name"));
	const { OUTPUT_DIR } = getConfig();
	const graph = await loadGraph(OUTPUT_DIR);

	// Find focus node (match by name, case-insensitive)
	const focusNode = graph.nodes.find(
		(n) => n.name.toLowerCase() === name.toLowerCase()
	);

	if (!focusNode) {
		return c.json({ focus: null, neighbors: [], edges: [] });
	}

	const focusKey = nodeKey(focusNode);

	// Find connected edges
	const connectedEdges = graph.edges.filter(
		(e) => e.source_key === focusKey || e.target_key === focusKey
	);

	// Find neighbor keys
	const neighborKeys = new Set<string>();
	for (const e of connectedEdges) {
		if (e.source_key !== focusKey) neighborKeys.add(e.source_key);
		if (e.target_key !== focusKey) neighborKeys.add(e.target_key);
	}

	// Build neighbor node map
	const keyToNode = new Map<string, RawNode>();
	for (const n of graph.nodes) {
		keyToNode.set(nodeKey(n), n);
	}

	const now = new Date();
	const neighbors = [...neighborKeys]
		.map((key) => {
			const n = keyToNode.get(key);
			if (!n) return null;
			return {
				name: n.name,
				type: n.node_type,
				relevance: Math.round(Math.exp(-0.1 * hoursAgo(n.last_seen, now) / 24) * 10000) / 10000,
				last_seen: n.last_seen,
			};
		})
		.filter((n): n is NonNullable<typeof n> => n !== null)
		.sort((a, b) => b.relevance - a.relevance)
		.slice(0, 50);

	return c.json({
		focus: {
			name: focusNode.name,
			type: focusNode.node_type,
			summary: String(focusNode.properties.summary ?? ""),
		},
		neighbors,
		edges: connectedEdges.map((e) => ({
			type: e.edge_type,
			source: e.source_key,
			target: e.target_key,
			weight: e.weight,
		})),
	});
});

export default app;
```

**Step 2: Register route in index.ts**

Add import and route registration in `web/server/index.ts`:

```typescript
import graph from "./routes/graph.js";
```

Add `app.route("/", graph);` with the other route registrations.

**Step 3: Verify TypeScript compiles**

Run: `cd web && npx tsc --noEmit`
Expected: 0 errors

**Step 4: Commit**

```bash
git add web/server/routes/graph.ts web/server/index.ts
git commit -m "feat(graph): add stats and about API endpoints"
```

---

### Task 3: Graph API — Activity Endpoint

**Files:**
- Modify: `web/server/routes/graph.ts`

**Step 1: Add activity endpoint**

Add to `web/server/routes/graph.ts`:

```typescript
// GET /api/graph/activity?hours=48
app.get("/api/graph/activity", async (c) => {
	const hours = Number(c.req.query("hours") ?? "48");
	const { OUTPUT_DIR } = getConfig();
	const graph = await loadGraph(OUTPUT_DIR);
	const now = new Date();

	// Filter session nodes within time window
	const sessionNodes = graph.nodes
		.filter((n) => n.node_type === "session" && hoursAgo(n.last_seen, now) <= hours)
		.sort((a, b) => new Date(b.last_seen).getTime() - new Date(a.last_seen).getTime());

	// Build node lookup
	const keyToNode = new Map<string, RawNode>();
	for (const n of graph.nodes) {
		keyToNode.set(nodeKey(n), n);
	}

	// Build edge lookup by source
	const edgesBySource = new Map<string, RawEdge[]>();
	const edgesByTarget = new Map<string, RawEdge[]>();
	for (const e of graph.edges) {
		if (!edgesBySource.has(e.source_key)) edgesBySource.set(e.source_key, []);
		edgesBySource.get(e.source_key)!.push(e);
		if (!edgesByTarget.has(e.target_key)) edgesByTarget.set(e.target_key, []);
		edgesByTarget.get(e.target_key)!.push(e);
	}

	// Build session data
	const sessions = sessionNodes.map((s) => {
		const sKey = nodeKey(s);
		const outEdges = edgesBySource.get(sKey) ?? [];

		const filesModified: string[] = [];
		const filesRead: string[] = [];
		const problems: { error: string; command: string; resolved: boolean }[] = [];
		const entities: string[] = [];
		let goal = "";
		const project = String(s.properties.project ?? "");

		for (const e of outEdges) {
			const target = keyToNode.get(e.target_key);
			if (!target) continue;

			if (target.node_type === "file" && e.edge_type === "modifies") {
				filesModified.push(target.name);
			} else if (target.node_type === "file" && e.edge_type === "reads") {
				filesRead.push(target.name);
			} else if (target.node_type === "problem") {
				problems.push({
					error: target.name,
					command: String(target.properties.command ?? ""),
					resolved: Boolean(target.properties.resolved ?? false),
				});
			} else if (target.node_type === "entity") {
				entities.push(target.name);
			} else if (target.node_type === "goal") {
				goal = target.name;
			}
		}

		return {
			id: s.name,
			summary: String(s.properties.summary ?? ""),
			hours_ago: Math.round(hoursAgo(s.last_seen, now) * 10) / 10,
			project,
			goal,
			files_modified: filesModified,
			files_read: filesRead,
			problems,
			entities,
		};
	});

	// Top entities (count across all time-windowed sessions)
	const entityCounts = new Map<string, number>();
	for (const s of sessions) {
		for (const e of s.entities) {
			entityCounts.set(e, (entityCounts.get(e) ?? 0) + 1);
		}
	}
	const topEntities = [...entityCounts.entries()]
		.sort((a, b) => b[1] - a[1])
		.slice(0, 15)
		.map(([name, count]) => ({ name, count }));

	// Active files (most recently modified)
	const fileLastSeen = new Map<string, number>();
	for (const s of sessions) {
		for (const f of s.files_modified) {
			const existing = fileLastSeen.get(f);
			if (existing === undefined || s.hours_ago < existing) {
				fileLastSeen.set(f, s.hours_ago);
			}
		}
	}
	const activeFiles = [...fileLastSeen.entries()]
		.sort((a, b) => a[1] - b[1])
		.slice(0, 20)
		.map(([path, h]) => ({ path, hours_ago: h }));

	// Stats
	const totalFiles = sessions.reduce((s, sess) => s + sess.files_modified.length, 0);
	const totalProblems = sessions.reduce((s, sess) => s + sess.problems.length, 0);

	return c.json({
		project: "(all)",
		time_window_hours: hours,
		sessions,
		top_entities: topEntities,
		active_files: activeFiles,
		stats: {
			session_count: sessions.length,
			avg_files_per_session: sessions.length > 0 ? Math.round((totalFiles / sessions.length) * 10) / 10 : 0,
			total_problems: totalProblems,
		},
	});
});
```

**Step 2: Verify TypeScript compiles**

Run: `cd web && npx tsc --noEmit`
Expected: 0 errors

**Step 3: Commit**

```bash
git add web/server/routes/graph.ts
git commit -m "feat(graph): add activity endpoint with session timeline data"
```

---

### Task 4: Graph API — Nodes + Insights Endpoints

**Files:**
- Modify: `web/server/routes/graph.ts`

**Step 1: Add nodes endpoint (for force graph)**

```typescript
// GET /api/graph/nodes?hours=48
app.get("/api/graph/nodes", async (c) => {
	const hours = Number(c.req.query("hours") ?? "48");
	const { OUTPUT_DIR } = getConfig();
	const graph = await loadGraph(OUTPUT_DIR);
	const now = new Date();

	// Filter nodes within time window
	const filteredNodes = graph.nodes
		.filter((n) => hoursAgo(n.last_seen, now) <= hours)
		.map((n) => ({
			id: n.id,
			node_type: n.node_type,
			name: n.name,
			properties: n.properties,
			first_seen: n.first_seen,
			last_seen: n.last_seen,
		}));

	// Build set of active node keys
	const activeKeys = new Set(filteredNodes.map((n) => `${n.node_type}:${n.name}`));

	// Filter edges where both endpoints are in the active set
	const filteredEdges = graph.edges
		.filter((e) => activeKeys.has(e.source_key) && activeKeys.has(e.target_key))
		.map((e) => ({
			id: e.id,
			source_key: e.source_key,
			target_key: e.target_key,
			edge_type: e.edge_type,
			weight: e.weight,
			properties: e.properties,
		}));

	return c.json({ nodes: filteredNodes, edges: filteredEdges });
});
```

**Step 2: Add insights endpoint**

This replicates the Python `GraphInsights` logic in TypeScript — all counting/grouping over nodes and edges.

```typescript
// GET /api/graph/insights?hours=48
app.get("/api/graph/insights", async (c) => {
	const hours = Number(c.req.query("hours") ?? "48");
	const { OUTPUT_DIR } = getConfig();
	const graph = await loadGraph(OUTPUT_DIR);
	const now = new Date();

	// Build lookups
	const keyToNode = new Map<string, RawNode>();
	for (const n of graph.nodes) keyToNode.set(nodeKey(n), n);

	const edgesBySource = new Map<string, RawEdge[]>();
	for (const e of graph.edges) {
		if (!edgesBySource.has(e.source_key)) edgesBySource.set(e.source_key, []);
		edgesBySource.get(e.source_key)!.push(e);
	}

	// Sessions in time window
	const sessions = graph.nodes.filter(
		(n) => n.node_type === "session" && hoursAgo(n.last_seen, now) <= hours
	);

	// --- Scope warnings: sessions with >5 files modified ---
	const scopeWarnings: { session_name: string; files_modified: number; project: string; problems_hit: number }[] = [];
	const fileModCounts = new Map<string, Set<string>>();  // file -> set of sessions
	const fileProblemCounts = new Map<string, number>();

	for (const s of sessions) {
		const sKey = nodeKey(s);
		const outEdges = edgesBySource.get(sKey) ?? [];
		const modFiles: string[] = [];
		let problems = 0;

		for (const e of outEdges) {
			const target = keyToNode.get(e.target_key);
			if (!target) continue;
			if (target.node_type === "file" && e.edge_type === "modifies") {
				modFiles.push(target.name);
				if (!fileModCounts.has(target.name)) fileModCounts.set(target.name, new Set());
				fileModCounts.get(target.name)!.add(s.name);
			}
			if (target.node_type === "problem") {
				problems++;
				// Track files associated with problems
				for (const f of modFiles) {
					fileProblemCounts.set(f, (fileProblemCounts.get(f) ?? 0) + 1);
				}
			}
		}

		if (modFiles.length > 5) {
			scopeWarnings.push({
				session_name: s.name,
				files_modified: modFiles.length,
				project: String(s.properties.project ?? ""),
				problems_hit: problems,
			});
		}
	}

	// --- Coupling clusters: file pairs co-modified in 3+ sessions ---
	const couplingClusters: { files: string[]; co_modification_count: number; description: string }[] = [];
	const sessionFiles = new Map<string, string[]>();  // session -> files modified
	for (const s of sessions) {
		const sKey = nodeKey(s);
		const outEdges = edgesBySource.get(sKey) ?? [];
		const files = outEdges
			.filter((e) => e.edge_type === "modifies" && keyToNode.get(e.target_key)?.node_type === "file")
			.map((e) => keyToNode.get(e.target_key)!.name);
		if (files.length > 1) sessionFiles.set(s.name, files);
	}

	const pairCounts = new Map<string, number>();
	for (const [, files] of sessionFiles) {
		for (let i = 0; i < files.length; i++) {
			for (let j = i + 1; j < files.length; j++) {
				const pair = [files[i]!, files[j]!].sort().join("|||");
				pairCounts.set(pair, (pairCounts.get(pair) ?? 0) + 1);
			}
		}
	}
	for (const [pair, count] of [...pairCounts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 10)) {
		if (count >= 3) {
			const [f1, f2] = pair.split("|||");
			couplingClusters.push({
				files: [f1!, f2!],
				co_modification_count: count,
				description: `Co-modified in ${count} sessions`,
			});
		}
	}

	// --- Error hotspots: files most associated with problems ---
	const errorHotspots = [...fileProblemCounts.entries()]
		.sort((a, b) => b[1] - a[1])
		.slice(0, 10)
		.filter(([, count]) => count > 0)
		.map(([file, count]) => ({
			file,
			problem_count: count,
			recent_problems: [] as string[],  // Could be enriched later
		}));

	// --- Recurring problems: patterns appearing 2+ times ---
	const problemCounts = new Map<string, { count: number; sessions: string[] }>();
	for (const s of sessions) {
		const sKey = nodeKey(s);
		const outEdges = edgesBySource.get(sKey) ?? [];
		for (const e of outEdges) {
			const target = keyToNode.get(e.target_key);
			if (target?.node_type === "problem") {
				const pattern = target.name.slice(0, 60);
				if (!problemCounts.has(pattern)) problemCounts.set(pattern, { count: 0, sessions: [] });
				const entry = problemCounts.get(pattern)!;
				entry.count++;
				if (entry.sessions.length < 5) entry.sessions.push(s.name);
			}
		}
	}
	const recurringProblems = [...problemCounts.entries()]
		.filter(([, v]) => v.count >= 2)
		.sort((a, b) => b[1].count - a[1].count)
		.slice(0, 10)
		.map(([pattern, v]) => ({
			pattern,
			occurrence_count: v.count,
			sessions: v.sessions,
		}));

	// Stats
	const totalFiles = sessions.reduce((sum, s) => {
		const sKey = nodeKey(s);
		const edges = edgesBySource.get(sKey) ?? [];
		return sum + edges.filter((e) => e.edge_type === "modifies").length;
	}, 0);

	return c.json({
		date: now.toISOString().split("T")[0],
		coupling_clusters: couplingClusters,
		error_hotspots: errorHotspots,
		scope_warnings: scopeWarnings,
		recurring_problems: recurringProblems,
		session_count: sessions.length,
		avg_files_per_session: sessions.length > 0 ? Math.round((totalFiles / sessions.length) * 10) / 10 : 0,
		total_problems: sessions.reduce((sum, s) => {
			const sKey = nodeKey(s);
			return sum + (edgesBySource.get(sKey) ?? []).filter((e) =>
				keyToNode.get(e.target_key)?.node_type === "problem"
			).length;
		}, 0),
	});
});
```

**Step 3: Verify TypeScript compiles**

Run: `cd web && npx tsc --noEmit`
Expected: 0 errors

**Step 4: Commit**

```bash
git add web/server/routes/graph.ts
git commit -m "feat(graph): add nodes and insights API endpoints"
```

---

### Task 5: API Tests

**Files:**
- Create: `web/server/__tests__/graph.test.ts`

**Step 1: Write tests**

Create `web/server/__tests__/graph.test.ts` following the seeds test pattern:

```typescript
import { afterAll, beforeEach, describe, expect, test } from "bun:test";
import { mkdir, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { app } from "../index.js";
import { resetConfig, setConfig } from "../lib/config.js";

const TMP_DIR = join(import.meta.dir, "fixtures", "_tmp_graph");

const SAMPLE_GRAPH = {
	nodes: [
		{
			id: "s1",
			node_type: "session",
			name: "session-abc",
			properties: { project: "distill", summary: "Fixed graph tests" },
			embedding: [],
			first_seen: new Date(Date.now() - 3600000).toISOString(),
			last_seen: new Date(Date.now() - 3600000).toISOString(),
			source_id: "abc",
		},
		{
			id: "p1",
			node_type: "project",
			name: "distill",
			properties: {},
			embedding: [],
			first_seen: new Date(Date.now() - 86400000).toISOString(),
			last_seen: new Date(Date.now() - 3600000).toISOString(),
			source_id: "",
		},
		{
			id: "f1",
			node_type: "file",
			name: "src/graph/store.py",
			properties: {},
			embedding: [],
			first_seen: new Date(Date.now() - 3600000).toISOString(),
			last_seen: new Date(Date.now() - 3600000).toISOString(),
			source_id: "",
		},
		{
			id: "f2",
			node_type: "file",
			name: "src/graph/query.py",
			properties: {},
			embedding: [],
			first_seen: new Date(Date.now() - 3600000).toISOString(),
			last_seen: new Date(Date.now() - 3600000).toISOString(),
			source_id: "",
		},
		{
			id: "pr1",
			node_type: "problem",
			name: "TypeError: cannot read property",
			properties: { command: "pytest", resolved: true },
			embedding: [],
			first_seen: new Date(Date.now() - 3600000).toISOString(),
			last_seen: new Date(Date.now() - 3600000).toISOString(),
			source_id: "",
		},
		{
			id: "e1",
			node_type: "entity",
			name: "pytest",
			properties: {},
			embedding: [],
			first_seen: new Date(Date.now() - 3600000).toISOString(),
			last_seen: new Date(Date.now() - 3600000).toISOString(),
			source_id: "",
		},
		{
			id: "g1",
			node_type: "goal",
			name: "Fix failing graph store tests",
			properties: {},
			embedding: [],
			first_seen: new Date(Date.now() - 3600000).toISOString(),
			last_seen: new Date(Date.now() - 3600000).toISOString(),
			source_id: "",
		},
	],
	edges: [
		{ id: "e-1", source_key: "session:session-abc", target_key: "project:distill", edge_type: "executes_in", weight: 1, properties: {}, created_at: new Date().toISOString() },
		{ id: "e-2", source_key: "session:session-abc", target_key: "file:src/graph/store.py", edge_type: "modifies", weight: 3, properties: {}, created_at: new Date().toISOString() },
		{ id: "e-3", source_key: "session:session-abc", target_key: "file:src/graph/query.py", edge_type: "modifies", weight: 1, properties: {}, created_at: new Date().toISOString() },
		{ id: "e-4", source_key: "session:session-abc", target_key: "problem:TypeError: cannot read property", edge_type: "produces", weight: 1, properties: {}, created_at: new Date().toISOString() },
		{ id: "e-5", source_key: "session:session-abc", target_key: "entity:pytest", edge_type: "uses", weight: 1, properties: {}, created_at: new Date().toISOString() },
		{ id: "e-6", source_key: "session:session-abc", target_key: "goal:Fix failing graph store tests", edge_type: "motivated_by", weight: 1, properties: {}, created_at: new Date().toISOString() },
	],
};

describe("Graph API", () => {
	beforeEach(async () => {
		await mkdir(TMP_DIR, { recursive: true });
		await writeFile(join(TMP_DIR, ".distill-graph.json"), JSON.stringify(SAMPLE_GRAPH), "utf-8");
		setConfig({ OUTPUT_DIR: TMP_DIR, PORT: 6109, PROJECT_DIR: "", POSTIZ_URL: "", POSTIZ_API_KEY: "" });
	});

	afterAll(async () => {
		resetConfig();
		await rm(TMP_DIR, { recursive: true, force: true });
	});

	test("GET /api/graph/stats returns counts", async () => {
		const res = await app.request("/api/graph/stats");
		expect(res.status).toBe(200);
		const data = await res.json();
		expect(data.total_nodes).toBe(7);
		expect(data.total_edges).toBe(6);
		expect(data.nodes_by_type.session).toBe(1);
		expect(data.nodes_by_type.file).toBe(2);
	});

	test("GET /api/graph/about/:name returns focus and neighbors", async () => {
		const res = await app.request("/api/graph/about/distill");
		expect(res.status).toBe(200);
		const data = await res.json();
		expect(data.focus).not.toBeNull();
		expect(data.focus.name).toBe("distill");
		expect(data.focus.type).toBe("project");
		expect(data.neighbors.length).toBeGreaterThan(0);
	});

	test("GET /api/graph/about/:name returns empty for unknown", async () => {
		const res = await app.request("/api/graph/about/nonexistent");
		expect(res.status).toBe(200);
		const data = await res.json();
		expect(data.focus).toBeNull();
		expect(data.neighbors).toHaveLength(0);
	});

	test("GET /api/graph/activity returns sessions", async () => {
		const res = await app.request("/api/graph/activity?hours=48");
		expect(res.status).toBe(200);
		const data = await res.json();
		expect(data.sessions).toHaveLength(1);
		expect(data.sessions[0].project).toBe("distill");
		expect(data.sessions[0].files_modified).toContain("src/graph/store.py");
		expect(data.sessions[0].entities).toContain("pytest");
		expect(data.stats.session_count).toBe(1);
	});

	test("GET /api/graph/nodes returns filtered nodes and edges", async () => {
		const res = await app.request("/api/graph/nodes?hours=48");
		expect(res.status).toBe(200);
		const data = await res.json();
		expect(data.nodes.length).toBeGreaterThan(0);
		expect(data.edges.length).toBeGreaterThan(0);
	});

	test("GET /api/graph/insights returns insight categories", async () => {
		const res = await app.request("/api/graph/insights?hours=48");
		expect(res.status).toBe(200);
		const data = await res.json();
		expect(data).toHaveProperty("coupling_clusters");
		expect(data).toHaveProperty("error_hotspots");
		expect(data).toHaveProperty("scope_warnings");
		expect(data).toHaveProperty("recurring_problems");
		expect(data).toHaveProperty("session_count");
	});

	test("GET /api/graph/stats handles missing file", async () => {
		await rm(join(TMP_DIR, ".distill-graph.json"));
		const res = await app.request("/api/graph/stats");
		expect(res.status).toBe(200);
		const data = await res.json();
		expect(data.total_nodes).toBe(0);
		expect(data.total_edges).toBe(0);
	});
});
```

**Step 2: Run tests**

Run: `cd web && bun test server/__tests__/graph.test.ts`
Expected: All tests pass

**Step 3: Commit**

```bash
git add web/server/__tests__/graph.test.ts
git commit -m "test(graph): add API endpoint tests"
```

---

### Task 6: Install react-force-graph-2d

**Files:**
- Modify: `web/package.json`

**Step 1: Install dependency**

Run: `cd web && bun add react-force-graph-2d`

**Step 2: Verify it installed**

Run: `cd web && bun run build`
Expected: Build succeeds

**Step 3: Commit**

```bash
git add web/package.json web/bun.lock
git commit -m "chore: add react-force-graph-2d dependency"
```

---

### Task 7: Frontend — Graph Page with Activity Tab

**Files:**
- Create: `web/src/routes/graph.tsx`
- Modify: `web/src/routeTree.gen.ts`
- Modify: `web/src/components/layout/Sidebar.tsx`

**Step 1: Create graph.tsx with Activity tab**

Create `web/src/routes/graph.tsx`. This is the largest frontend file. It contains:

- Tab state: `"activity" | "explorer" | "insights"`
- Time window state: `24 | 48 | 168 | 720` hours
- Activity tab: stats strip + session timeline cards
- Explorer and Insights tabs as placeholders (filled in Tasks 8 and 9)

Key patterns to follow from `reading.tsx`:
- `useQuery` with `queryKey` including the time window param
- Tab buttons with active styling
- Cards with Tailwind styling

The Activity tab layout:
1. **Stats strip** — 4 stat cards (sessions, files/session, problems, entities)
2. **Session timeline** — vertical list of session cards, each showing:
   - Project badge + relative time ("2h ago")
   - Goal text
   - File chips (green), problem chips (red), entity chips (blue)

```typescript
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import type { GraphActivityResponse, GraphInsightsResponse, GraphNodesResponse } from "../../shared/schemas.js";

type Tab = "activity" | "explorer" | "insights";
type TimeWindow = 24 | 48 | 168 | 720;

const TIME_OPTIONS: { value: TimeWindow; label: string }[] = [
	{ value: 24, label: "24h" },
	{ value: 48, label: "48h" },
	{ value: 168, label: "7d" },
	{ value: 720, label: "30d" },
];

export default function GraphPage() {
	const [activeTab, setActiveTab] = useState<Tab>("activity");
	const [hours, setHours] = useState<TimeWindow>(48);

	return (
		<div className="mx-auto max-w-6xl space-y-6 p-4 md:p-6">
			<div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
				<h1 className="text-2xl font-bold">Knowledge Graph</h1>
				<div className="flex gap-1 rounded-lg bg-zinc-100 p-1 dark:bg-zinc-800">
					{TIME_OPTIONS.map((opt) => (
						<button
							key={opt.value}
							onClick={() => setHours(opt.value)}
							className={`rounded-md px-3 py-1 text-sm font-medium transition-colors ${
								hours === opt.value
									? "bg-white text-zinc-900 shadow-sm dark:bg-zinc-700 dark:text-zinc-100"
									: "text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-200"
							}`}
						>
							{opt.label}
						</button>
					))}
				</div>
			</div>

			{/* Tab bar */}
			<div className="flex gap-1 border-b border-zinc-200 dark:border-zinc-700">
				{(["activity", "explorer", "insights"] as Tab[]).map((tab) => (
					<button
						key={tab}
						onClick={() => setActiveTab(tab)}
						className={`px-4 py-2 text-sm font-medium capitalize transition-colors border-b-2 -mb-px ${
							activeTab === tab
								? "border-indigo-500 text-indigo-600 dark:text-indigo-400"
								: "border-transparent text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300"
						}`}
					>
						{tab}
					</button>
				))}
			</div>

			{activeTab === "activity" && <ActivityTab hours={hours} />}
			{activeTab === "explorer" && <ExplorerTab hours={hours} />}
			{activeTab === "insights" && <InsightsTab hours={hours} />}
		</div>
	);
}

function ActivityTab({ hours }: { hours: TimeWindow }) {
	const { data, isLoading } = useQuery<GraphActivityResponse>({
		queryKey: ["graph-activity", hours],
		queryFn: async () => {
			const res = await fetch(`/api/graph/activity?hours=${hours}`);
			if (!res.ok) throw new Error("Failed to load graph activity");
			return res.json();
		},
	});

	if (isLoading) return <div className="text-zinc-500">Loading activity...</div>;
	if (!data) return <div className="text-zinc-500">No graph data found. Run <code>distill graph build</code> first.</div>;

	const { sessions, top_entities: topEntities, stats } = data;

	return (
		<div className="space-y-6">
			{/* Stats strip */}
			<div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
				<StatCard label="Sessions" value={stats.session_count} />
				<StatCard label="Files/session" value={stats.avg_files_per_session} />
				<StatCard label="Problems" value={stats.total_problems} />
				<StatCard label="Entities" value={topEntities.length} />
			</div>

			{/* Top entities */}
			{topEntities.length > 0 && (
				<div>
					<h3 className="mb-2 text-sm font-medium text-zinc-500">What's on your mind</h3>
					<div className="flex flex-wrap gap-2">
						{topEntities.map((e) => (
							<span
								key={e.name}
								className="inline-flex items-center gap-1 rounded-full bg-indigo-50 px-3 py-1 text-sm text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300"
							>
								{e.name}
								<span className="text-xs text-indigo-400">{e.count}</span>
							</span>
						))}
					</div>
				</div>
			)}

			{/* Session timeline */}
			<div className="space-y-3">
				<h3 className="text-sm font-medium text-zinc-500">Session timeline</h3>
				{sessions.length === 0 ? (
					<p className="text-sm text-zinc-400">No sessions in this time window.</p>
				) : (
					<div className="relative space-y-4 pl-6 before:absolute before:left-2 before:top-2 before:bottom-2 before:w-0.5 before:bg-zinc-200 dark:before:bg-zinc-700">
						{sessions.map((s) => (
							<div key={s.id} className="relative">
								{/* Timeline dot */}
								<div className="absolute -left-6 top-2 h-3 w-3 rounded-full border-2 border-indigo-400 bg-white dark:bg-zinc-900" />

								<div className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-700">
									<div className="flex items-start justify-between gap-2">
										<div className="flex items-center gap-2">
											{s.project && (
												<span className="rounded bg-purple-100 px-2 py-0.5 text-xs font-medium text-purple-700 dark:bg-purple-950 dark:text-purple-300">
													{s.project}
												</span>
											)}
											<span className="text-xs text-zinc-400">
												{s.hours_ago < 1 ? "just now" : `${Math.round(s.hours_ago)}h ago`}
											</span>
										</div>
										{s.problems.length > 0 && (
											<span className="rounded bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700 dark:bg-red-950 dark:text-red-300">
												{s.problems.length} problem{s.problems.length > 1 ? "s" : ""}
											</span>
										)}
									</div>

									{/* Goal */}
									{s.goal && (
										<p className="mt-2 text-sm text-zinc-700 dark:text-zinc-300">{s.goal}</p>
									)}
									{!s.goal && s.summary && (
										<p className="mt-2 text-sm text-zinc-700 dark:text-zinc-300">{s.summary}</p>
									)}

									{/* File chips */}
									{s.files_modified.length > 0 && (
										<div className="mt-2 flex flex-wrap gap-1">
											{s.files_modified.slice(0, 8).map((f) => (
												<span key={f} className="rounded bg-green-50 px-1.5 py-0.5 text-xs text-green-700 dark:bg-green-950 dark:text-green-300">
													{f.split("/").pop()}
												</span>
											))}
											{s.files_modified.length > 8 && (
												<span className="text-xs text-zinc-400">+{s.files_modified.length - 8} more</span>
											)}
										</div>
									)}

									{/* Entity chips */}
									{s.entities.length > 0 && (
										<div className="mt-1 flex flex-wrap gap-1">
											{s.entities.map((e) => (
												<span key={e} className="rounded bg-blue-50 px-1.5 py-0.5 text-xs text-blue-700 dark:bg-blue-950 dark:text-blue-300">
													{e}
												</span>
											))}
										</div>
									)}
								</div>
							</div>
						))}
					</div>
				)}
			</div>
		</div>
	);
}

function StatCard({ label, value }: { label: string; value: number }) {
	return (
		<div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
			<div className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">{value}</div>
			<div className="text-xs text-zinc-500">{label}</div>
		</div>
	);
}

// Placeholder — implemented in Task 8
function ExplorerTab({ hours }: { hours: TimeWindow }) {
	return <div className="text-zinc-500">Explorer tab — coming next.</div>;
}

// Placeholder — implemented in Task 9
function InsightsTab({ hours }: { hours: TimeWindow }) {
	return <div className="text-zinc-500">Insights tab — coming next.</div>;
}
```

**Step 2: Register route in routeTree.gen.ts**

Add import and route definition:

```typescript
import GraphPage from "./routes/graph.js";

const graphRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/graph",
  component: GraphPage,
});
```

Add `graphRoute` to the `routeTree.addChildren([...])` array.

**Step 3: Add to Sidebar**

In `web/src/components/layout/Sidebar.tsx`:
- Add `Network` to the lucide-react import
- Add `{ to: "/graph", label: "Graph", icon: Network }` to both `navItems` and `mobileTabItems`

**Step 4: Verify build**

Run: `cd web && bun run build`
Expected: Build succeeds

**Step 5: Commit**

```bash
git add web/src/routes/graph.tsx web/src/routeTree.gen.ts web/src/components/layout/Sidebar.tsx
git commit -m "feat(graph): add graph page with activity tab and navigation"
```

---

### Task 8: Frontend — Explorer Tab (Force Graph)

**Files:**
- Modify: `web/src/routes/graph.tsx`

**Step 1: Replace ExplorerTab placeholder**

Replace the placeholder `ExplorerTab` function with the full force-directed graph implementation:

```typescript
import ForceGraph2D from "react-force-graph-2d";
import { useRef, useCallback, useMemo } from "react";

// Node type → color mapping
const NODE_COLORS: Record<string, string> = {
	session: "#6366f1",   // indigo
	project: "#a855f7",   // purple
	file: "#22c55e",      // green
	problem: "#ef4444",   // red
	entity: "#f97316",    // orange
	goal: "#eab308",      // yellow
	thread: "#06b6d4",    // cyan
	decision: "#8b5cf6",  // violet
	insight: "#14b8a6",   // teal
	artifact: "#64748b",  // slate
};

function ExplorerTab({ hours }: { hours: TimeWindow }) {
	const [selectedNode, setSelectedNode] = useState<{
		name: string;
		type: string;
		summary: string;
		neighbors: { name: string; type: string; relevance: number }[];
		edges: { type: string; source: string; target: string; weight: number }[];
	} | null>(null);
	const [searchQuery, setSearchQuery] = useState("");
	const [hiddenTypes, setHiddenTypes] = useState<Set<string>>(new Set());
	const graphRef = useRef<any>(null);

	const { data, isLoading } = useQuery<GraphNodesResponse>({
		queryKey: ["graph-nodes", hours],
		queryFn: async () => {
			const res = await fetch(`/api/graph/nodes?hours=${hours}`);
			if (!res.ok) throw new Error("Failed to load graph nodes");
			return res.json();
		},
	});

	// Transform data for force graph
	const graphData = useMemo(() => {
		if (!data) return { nodes: [], links: [] };

		const filteredNodes = data.nodes.filter((n) => !hiddenTypes.has(n.node_type));
		const nodeKeys = new Set(filteredNodes.map((n) => `${n.node_type}:${n.name}`));

		const nodes = filteredNodes.map((n) => ({
			id: `${n.node_type}:${n.name}`,
			name: n.name,
			type: n.node_type,
			color: NODE_COLORS[n.node_type] ?? "#94a3b8",
			val: 1,
		}));

		const links = data.edges
			.filter((e) => nodeKeys.has(e.source_key) && nodeKeys.has(e.target_key))
			.map((e) => ({
				source: e.source_key,
				target: e.target_key,
				type: e.edge_type,
				weight: e.weight,
			}));

		return { nodes, links };
	}, [data, hiddenTypes]);

	const handleNodeClick = useCallback(async (node: any) => {
		const name = node.name;
		try {
			const res = await fetch(`/api/graph/about/${encodeURIComponent(name)}`);
			if (res.ok) {
				const aboutData = await res.json();
				setSelectedNode({
					name: aboutData.focus?.name ?? name,
					type: aboutData.focus?.type ?? node.type,
					summary: aboutData.focus?.summary ?? "",
					neighbors: aboutData.neighbors,
					edges: aboutData.edges,
				});
			}
		} catch {
			setSelectedNode({
				name,
				type: node.type,
				summary: "",
				neighbors: [],
				edges: [],
			});
		}
	}, []);

	// Search: center on matching node
	const handleSearch = useCallback(() => {
		if (!searchQuery || !graphRef.current) return;
		const node = graphData.nodes.find((n) =>
			n.name.toLowerCase().includes(searchQuery.toLowerCase())
		);
		if (node) {
			graphRef.current.centerAt((node as any).x, (node as any).y, 500);
			graphRef.current.zoom(3, 500);
			handleNodeClick(node);
		}
	}, [searchQuery, graphData, handleNodeClick]);

	const nodeTypes = useMemo(() => {
		if (!data) return [];
		const types = new Set(data.nodes.map((n) => n.node_type));
		return [...types].sort();
	}, [data]);

	if (isLoading) return <div className="text-zinc-500">Loading graph...</div>;
	if (!data || data.nodes.length === 0) return <div className="text-zinc-500">No graph data in this time window.</div>;

	return (
		<div className="space-y-4">
			{/* Controls */}
			<div className="flex flex-wrap items-center gap-4">
				<div className="flex gap-2">
					<input
						type="text"
						value={searchQuery}
						onChange={(e) => setSearchQuery(e.target.value)}
						onKeyDown={(e) => e.key === "Enter" && handleSearch()}
						placeholder="Search nodes..."
						className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-600 dark:bg-zinc-800"
					/>
					<button onClick={handleSearch} className="rounded-md bg-indigo-600 px-3 py-1.5 text-sm text-white hover:bg-indigo-700">
						Find
					</button>
				</div>
				<div className="flex flex-wrap gap-2">
					{nodeTypes.map((type) => (
						<label key={type} className="flex items-center gap-1 text-xs">
							<input
								type="checkbox"
								checked={!hiddenTypes.has(type)}
								onChange={() => {
									setHiddenTypes((prev) => {
										const next = new Set(prev);
										if (next.has(type)) next.delete(type);
										else next.add(type);
										return next;
									});
								}}
							/>
							<span className="inline-block h-2.5 w-2.5 rounded-full" style={{ backgroundColor: NODE_COLORS[type] ?? "#94a3b8" }} />
							{type}
						</label>
					))}
				</div>
			</div>

			{/* Graph + detail panel */}
			<div className="flex gap-4">
				<div className="flex-1 rounded-lg border border-zinc-200 dark:border-zinc-700 overflow-hidden" style={{ height: 500 }}>
					<ForceGraph2D
						ref={graphRef}
						graphData={graphData}
						nodeLabel="name"
						nodeColor="color"
						nodeVal="val"
						linkDirectionalArrowLength={3}
						linkDirectionalArrowRelPos={1}
						linkWidth={(link: any) => Math.min(link.weight, 5)}
						linkColor={() => "#94a3b8"}
						onNodeClick={handleNodeClick}
						nodeCanvasObject={(node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
							const label = node.name.split("/").pop() ?? node.name;
							const fontSize = Math.max(10 / globalScale, 1.5);
							const r = Math.max(3, Math.sqrt(node.val ?? 1) * 3);

							ctx.beginPath();
							ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
							ctx.fillStyle = node.color;
							ctx.fill();

							if (globalScale > 1.5) {
								ctx.font = `${fontSize}px Sans-Serif`;
								ctx.textAlign = "center";
								ctx.textBaseline = "top";
								ctx.fillStyle = "#666";
								ctx.fillText(label.slice(0, 20), node.x, node.y + r + 1);
							}
						}}
					/>
				</div>

				{/* Detail panel */}
				{selectedNode && (
					<div className="w-72 shrink-0 space-y-3 rounded-lg border border-zinc-200 p-4 dark:border-zinc-700">
						<div className="flex items-center justify-between">
							<span className="rounded px-2 py-0.5 text-xs font-medium" style={{ backgroundColor: `${NODE_COLORS[selectedNode.type] ?? "#94a3b8"}20`, color: NODE_COLORS[selectedNode.type] ?? "#94a3b8" }}>
								{selectedNode.type}
							</span>
							<button onClick={() => setSelectedNode(null)} className="text-xs text-zinc-400 hover:text-zinc-600">&times;</button>
						</div>
						<h3 className="text-sm font-semibold break-all">{selectedNode.name}</h3>
						{selectedNode.summary && <p className="text-xs text-zinc-500">{selectedNode.summary}</p>}

						{selectedNode.neighbors.length > 0 && (
							<div>
								<h4 className="text-xs font-medium text-zinc-400 mb-1">Connected ({selectedNode.neighbors.length})</h4>
								<div className="max-h-48 space-y-1 overflow-y-auto">
									{selectedNode.neighbors.slice(0, 20).map((n) => (
										<div key={n.name} className="flex items-center justify-between text-xs">
											<span className="truncate">{n.name}</span>
											<span className="ml-1 shrink-0 rounded px-1 text-xs" style={{ backgroundColor: `${NODE_COLORS[n.type] ?? "#94a3b8"}20`, color: NODE_COLORS[n.type] ?? "#94a3b8" }}>
												{n.type}
											</span>
										</div>
									))}
								</div>
							</div>
						)}
					</div>
				)}
			</div>
		</div>
	);
}
```

Note: You'll need to add `useRef` and `useMemo` to the React import at the top, and add the `ForceGraph2D` import. The `useState` for `selectedNode`, `searchQuery`, `hiddenTypes` goes inside the `ExplorerTab` component.

**Step 2: Verify build**

Run: `cd web && bun run build`
Expected: Build succeeds

**Step 3: Commit**

```bash
git add web/src/routes/graph.tsx
git commit -m "feat(graph): add explorer tab with force-directed graph visualization"
```

---

### Task 9: Frontend — Insights Tab

**Files:**
- Modify: `web/src/routes/graph.tsx`

**Step 1: Replace InsightsTab placeholder**

```typescript
function InsightsTab({ hours }: { hours: TimeWindow }) {
	const { data, isLoading } = useQuery<GraphInsightsResponse>({
		queryKey: ["graph-insights", hours],
		queryFn: async () => {
			const res = await fetch(`/api/graph/insights?hours=${hours}`);
			if (!res.ok) throw new Error("Failed to load insights");
			return res.json();
		},
	});

	if (isLoading) return <div className="text-zinc-500">Loading insights...</div>;
	if (!data) return <div className="text-zinc-500">No insights available.</div>;

	return (
		<div className="space-y-6">
			{/* Stats strip */}
			<div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
				<StatCard label="Sessions" value={data.session_count} />
				<StatCard label="Avg files/session" value={data.avg_files_per_session} />
				<StatCard label="Total problems" value={data.total_problems} />
			</div>

			{/* Scope warnings */}
			{data.scope_warnings.length > 0 && (
				<InsightSection
					title="Scope Warnings"
					subtitle="Sessions touching >5 files have 78% error rate historically"
					icon="⚠️"
					count={data.scope_warnings.length}
				>
					{data.scope_warnings.map((w) => (
						<div key={w.session_name} className="flex items-center justify-between rounded border border-amber-200 bg-amber-50 p-3 text-sm dark:border-amber-900 dark:bg-amber-950">
							<div>
								<span className="font-medium">{w.session_name.slice(0, 12)}...</span>
								{w.project && <span className="ml-2 text-xs text-zinc-500">[{w.project}]</span>}
							</div>
							<div className="flex items-center gap-2 text-xs">
								<span className="text-amber-600">{w.files_modified} files</span>
								{w.problems_hit > 0 && <span className="text-red-600">{w.problems_hit} problems</span>}
							</div>
						</div>
					))}
				</InsightSection>
			)}

			{/* Error hotspots */}
			{data.error_hotspots.length > 0 && (
				<InsightSection
					title="Error Hotspots"
					subtitle="Files most associated with problems"
					icon="🔥"
					count={data.error_hotspots.length}
				>
					{data.error_hotspots.map((h) => (
						<div key={h.file} className="flex items-center justify-between rounded border border-red-200 bg-red-50 p-3 text-sm dark:border-red-900 dark:bg-red-950">
							<span className="font-mono text-xs">{h.file}</span>
							<span className="text-xs text-red-600">{h.problem_count} problems</span>
						</div>
					))}
				</InsightSection>
			)}

			{/* Coupling clusters */}
			{data.coupling_clusters.length > 0 && (
				<InsightSection
					title="Architectural Coupling"
					subtitle="File pairs that always change together"
					icon="🔗"
					count={data.coupling_clusters.length}
				>
					{data.coupling_clusters.map((cl, i) => (
						<div key={i} className="flex items-center justify-between rounded border border-blue-200 bg-blue-50 p-3 text-sm dark:border-blue-900 dark:bg-blue-950">
							<div className="space-y-0.5">
								{cl.files.map((f) => (
									<div key={f} className="font-mono text-xs">{f}</div>
								))}
							</div>
							<span className="text-xs text-blue-600">{cl.co_modification_count}x together</span>
						</div>
					))}
				</InsightSection>
			)}

			{/* Recurring problems */}
			{data.recurring_problems.length > 0 && (
				<InsightSection
					title="Recurring Problems"
					subtitle="Error patterns appearing across multiple sessions"
					icon="🔄"
					count={data.recurring_problems.length}
				>
					{data.recurring_problems.map((p) => (
						<div key={p.pattern} className="rounded border border-zinc-200 p-3 dark:border-zinc-700">
							<div className="text-sm font-medium">{p.pattern}</div>
							<div className="mt-1 text-xs text-zinc-500">
								{p.occurrence_count} occurrences across {p.sessions.length} session{p.sessions.length > 1 ? "s" : ""}
							</div>
						</div>
					))}
				</InsightSection>
			)}

			{/* Empty state */}
			{data.scope_warnings.length === 0 && data.error_hotspots.length === 0 &&
			 data.coupling_clusters.length === 0 && data.recurring_problems.length === 0 && (
				<p className="text-sm text-zinc-400">No patterns detected in this time window. Try expanding to 7d or 30d.</p>
			)}
		</div>
	);
}

function InsightSection({ title, subtitle, icon, count, children }: {
	title: string;
	subtitle: string;
	icon: string;
	count: number;
	children: React.ReactNode;
}) {
	return (
		<div>
			<div className="mb-2 flex items-center gap-2">
				<span>{icon}</span>
				<h3 className="text-sm font-semibold">{title}</h3>
				<span className="rounded-full bg-zinc-100 px-2 py-0.5 text-xs dark:bg-zinc-800">{count}</span>
			</div>
			<p className="mb-3 text-xs text-zinc-500">{subtitle}</p>
			<div className="space-y-2">{children}</div>
		</div>
	);
}
```

**Step 2: Verify build**

Run: `cd web && bun run build`
Expected: Build succeeds

**Step 3: Commit**

```bash
git add web/src/routes/graph.tsx
git commit -m "feat(graph): add insights tab with pattern cards"
```

---

### Task 10: Verification

**Step 1: Run all server tests**

Run: `cd web && bun test server`
Expected: All tests pass (existing + new graph tests)

**Step 2: Run frontend tests**

Run: `cd web && bun test src`
Expected: All tests pass

**Step 3: Full build**

Run: `cd web && bun run build`
Expected: Build succeeds

**Step 4: Manual smoke test**

Start the server:
```bash
cd web && bun run dev
```

Visit `http://localhost:6108/graph` and verify:
1. Activity tab shows session timeline with stats
2. Explorer tab shows force-directed graph with clickable nodes
3. Insights tab shows pattern cards
4. Time window toggle updates all tabs
5. Graph nav item appears in sidebar

**Step 5: Final commit (if any cleanup needed)**

```bash
git add -A
git commit -m "feat(graph): knowledge graph dashboard — activity, explorer, insights"
```
