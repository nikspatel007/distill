import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { Hono } from "hono";
import { z } from "zod";
import {
	GraphEdgeSchema,
	GraphNodeSchema,
	type GraphNode,
	type GraphEdge,
} from "../../shared/schemas.js";
import { getConfig } from "../lib/config.js";

const app = new Hono();

const GRAPH_FILE = ".distill-graph.json";

const GraphFileSchema = z.object({
	nodes: z.array(GraphNodeSchema).default([]),
	edges: z.array(GraphEdgeSchema).default([]),
});

type GraphData = z.infer<typeof GraphFileSchema>;

async function loadGraph(): Promise<GraphData> {
	try {
		const { OUTPUT_DIR } = getConfig();
		const raw = await readFile(join(OUTPUT_DIR, GRAPH_FILE), "utf-8");
		return GraphFileSchema.parse(JSON.parse(raw));
	} catch {
		return { nodes: [], edges: [] };
	}
}

function nodeKey(node: GraphNode): string {
	return `${node.node_type}:${node.name}`;
}

function hoursAgo(isoString: string): number {
	const now = Date.now();
	const then = new Date(isoString).getTime();
	return (now - then) / (1000 * 60 * 60);
}

// ---------- GET /api/graph/stats ----------

app.get("/api/graph/stats", async (c) => {
	const { nodes, edges } = await loadGraph();

	const nodesByType: Record<string, number> = {};
	for (const n of nodes) {
		nodesByType[n.node_type] = (nodesByType[n.node_type] ?? 0) + 1;
	}

	const edgesByType: Record<string, number> = {};
	for (const e of edges) {
		edgesByType[e.edge_type] = (edgesByType[e.edge_type] ?? 0) + 1;
	}

	return c.json({
		total_nodes: nodes.length,
		total_edges: edges.length,
		nodes_by_type: nodesByType,
		edges_by_type: edgesByType,
	});
});

// ---------- GET /api/graph/about/:name ----------

app.get("/api/graph/about/:name", async (c) => {
	const name = decodeURIComponent(c.req.param("name"));
	const { nodes, edges } = await loadGraph();

	// Build key->node index
	const keyToNode = new Map<string, GraphNode>();
	for (const n of nodes) {
		keyToNode.set(nodeKey(n), n);
	}

	// Find focus node — match by name (any type)
	const focusNode = nodes.find((n) => n.name === name) ?? null;

	if (!focusNode) {
		return c.json({
			focus: null,
			neighbors: [],
			edges: [],
		});
	}

	const focusKey = nodeKey(focusNode);

	// BFS 1-hop: find edges touching focus
	const relevantEdges: Array<{
		type: string;
		source: string;
		target: string;
		weight: number;
	}> = [];
	const neighborKeys = new Set<string>();

	for (const e of edges) {
		if (e.source_key === focusKey) {
			neighborKeys.add(e.target_key);
			relevantEdges.push({
				type: e.edge_type,
				source: e.source_key,
				target: e.target_key,
				weight: e.weight,
			});
		} else if (e.target_key === focusKey) {
			neighborKeys.add(e.source_key);
			relevantEdges.push({
				type: e.edge_type,
				source: e.source_key,
				target: e.target_key,
				weight: e.weight,
			});
		}
	}

	// Build neighbor list with exponential decay relevance on last_seen
	const now = Date.now();
	const neighbors: Array<{
		name: string;
		type: string;
		relevance: number;
		last_seen: string;
	}> = [];

	for (const key of neighborKeys) {
		const n = keyToNode.get(key);
		if (!n) continue;

		const hoursSinceSeen = (now - new Date(n.last_seen).getTime()) / (1000 * 60 * 60);
		// Exponential decay: half-life of 24 hours
		const relevance = Math.exp(-0.693 * hoursSinceSeen / 24);

		neighbors.push({
			name: n.name,
			type: n.node_type,
			relevance: Math.round(relevance * 1000) / 1000,
			last_seen: n.last_seen,
		});
	}

	// Sort by relevance descending
	neighbors.sort((a, b) => b.relevance - a.relevance);

	return c.json({
		focus: {
			name: focusNode.name,
			type: focusNode.node_type,
			summary: (focusNode.properties["summary"] as string) ?? "",
		},
		neighbors,
		edges: relevantEdges,
	});
});

// ---------- GET /api/graph/activity ----------

app.get("/api/graph/activity", async (c) => {
	const hours = Number(c.req.query("hours") ?? "48");
	const { nodes, edges } = await loadGraph();

	// Build key->node index
	const keyToNode = new Map<string, GraphNode>();
	for (const n of nodes) {
		keyToNode.set(nodeKey(n), n);
	}

	// Build adjacency: source_key -> edges, target_key -> edges
	const outEdges = new Map<string, GraphEdge[]>();
	const inEdges = new Map<string, GraphEdge[]>();
	for (const e of edges) {
		const out = outEdges.get(e.source_key) ?? [];
		out.push(e);
		outEdges.set(e.source_key, out);

		const inp = inEdges.get(e.target_key) ?? [];
		inp.push(e);
		inEdges.set(e.target_key, inp);
	}

	// Find session nodes within time window
	const sessionNodes = nodes.filter(
		(n) => n.node_type === "session" && hoursAgo(n.last_seen) <= hours,
	);

	const entityCounts = new Map<string, number>();
	const fileLastSeen = new Map<string, number>();

	const sessions = sessionNodes.map((sn) => {
		const sKey = nodeKey(sn);
		const allEdges = [...(outEdges.get(sKey) ?? []), ...(inEdges.get(sKey) ?? [])];

		let project = "";
		let goal = "";
		const filesModified: string[] = [];
		const filesRead: string[] = [];
		const problems: Array<{ error: string; command: string; resolved: boolean }> = [];
		const entities: string[] = [];

		for (const e of allEdges) {
			const otherKey = e.source_key === sKey ? e.target_key : e.source_key;
			const other = keyToNode.get(otherKey);
			if (!other) continue;

			switch (other.node_type) {
				case "project":
					project = other.name;
					break;
				case "goal":
					goal = other.name;
					break;
				case "file":
					if (e.edge_type === "modifies") {
						filesModified.push(other.name);
						const ha = hoursAgo(other.last_seen);
						const prev = fileLastSeen.get(other.name);
						if (prev === undefined || ha < prev) {
							fileLastSeen.set(other.name, ha);
						}
					} else if (e.edge_type === "reads") {
						filesRead.push(other.name);
					}
					break;
				case "problem":
					problems.push({
						error: other.name,
						command: (other.properties["command"] as string) ?? "",
						resolved: (other.properties["resolved"] as boolean) ?? false,
					});
					break;
				case "entity":
					entities.push(other.name);
					entityCounts.set(other.name, (entityCounts.get(other.name) ?? 0) + 1);
					break;
			}
		}

		return {
			id: sn.id,
			summary: (sn.properties["summary"] as string) ?? sn.name,
			hours_ago: Math.round(hoursAgo(sn.last_seen) * 10) / 10,
			project,
			goal,
			files_modified: filesModified,
			files_read: filesRead,
			problems,
			entities,
		};
	});

	// Sort sessions by most recent first
	sessions.sort((a, b) => a.hours_ago - b.hours_ago);

	// Top entities by count
	const topEntities = [...entityCounts.entries()]
		.map(([name, count]) => ({ name, count }))
		.sort((a, b) => b.count - a.count)
		.slice(0, 20);

	// Active files sorted by most recently modified
	const activeFiles = [...fileLastSeen.entries()]
		.map(([path, ha]) => ({ path, hours_ago: Math.round(ha * 10) / 10 }))
		.sort((a, b) => a.hours_ago - b.hours_ago)
		.slice(0, 30);

	const totalFiles = sessions.reduce((sum, s) => sum + s.files_modified.length, 0);
	const totalProblems = sessions.reduce((sum, s) => sum + s.problems.length, 0);

	return c.json({
		project: "",
		time_window_hours: hours,
		sessions,
		top_entities: topEntities,
		active_files: activeFiles,
		stats: {
			session_count: sessions.length,
			avg_files_per_session:
				sessions.length > 0 ? Math.round((totalFiles / sessions.length) * 10) / 10 : 0,
			total_problems: totalProblems,
		},
	});
});

// ---------- GET /api/graph/nodes ----------

app.get("/api/graph/nodes", async (c) => {
	const hours = Number(c.req.query("hours") ?? "48");
	const { nodes, edges } = await loadGraph();

	// Filter nodes by last_seen within time window
	const activeNodes = nodes
		.filter((n) => hoursAgo(n.last_seen) <= hours)
		.map((n) => {
			// Strip embeddings from properties
			const { embedding, ...rest } = n.properties as Record<string, unknown>;
			return { ...n, properties: rest };
		});

	// Build set of active node keys
	const activeKeys = new Set(activeNodes.map((n) => nodeKey(n)));

	// Filter edges where both endpoints are in the active set
	const activeEdges = edges.filter(
		(e) => activeKeys.has(e.source_key) && activeKeys.has(e.target_key),
	);

	return c.json({
		nodes: activeNodes,
		edges: activeEdges,
	});
});

// ---------- GET /api/graph/insights ----------

app.get("/api/graph/insights", async (c) => {
	const hours = Number(c.req.query("hours") ?? "48");
	const { nodes, edges } = await loadGraph();

	// Build key->node index
	const keyToNode = new Map<string, GraphNode>();
	for (const n of nodes) {
		keyToNode.set(nodeKey(n), n);
	}

	// Build adjacency
	const outEdges = new Map<string, GraphEdge[]>();
	const inEdges = new Map<string, GraphEdge[]>();
	for (const e of edges) {
		const out = outEdges.get(e.source_key) ?? [];
		out.push(e);
		outEdges.set(e.source_key, out);

		const inp = inEdges.get(e.target_key) ?? [];
		inp.push(e);
		inEdges.set(e.target_key, inp);
	}

	// Find session nodes within time window
	const sessionNodes = nodes.filter(
		(n) => n.node_type === "session" && hoursAgo(n.last_seen) <= hours,
	);

	// Collect per-session data
	const sessionFiles = new Map<string, string[]>(); // session name -> files modified
	const sessionProblems = new Map<string, string[]>(); // session name -> problem names
	const sessionProjects = new Map<string, string>(); // session name -> project
	const fileProblemCounts = new Map<string, string[]>(); // file -> problem list

	for (const sn of sessionNodes) {
		const sKey = nodeKey(sn);
		const allEdges = [...(outEdges.get(sKey) ?? []), ...(inEdges.get(sKey) ?? [])];
		const files: string[] = [];
		const probs: string[] = [];

		for (const e of allEdges) {
			const otherKey = e.source_key === sKey ? e.target_key : e.source_key;
			const other = keyToNode.get(otherKey);
			if (!other) continue;

			if (other.node_type === "file" && e.edge_type === "modifies") {
				files.push(other.name);
			}
			if (other.node_type === "problem") {
				probs.push(other.name);
				const fp = fileProblemCounts.get(other.name) ?? [];
				// Associate problems with files for hotspots
				for (const f of files) {
					const existing = fileProblemCounts.get(f) ?? [];
					if (!existing.includes(other.name)) {
						existing.push(other.name);
					}
					fileProblemCounts.set(f, existing);
				}
			}
			if (other.node_type === "project") {
				sessionProjects.set(sn.name, other.name);
			}
		}

		sessionFiles.set(sn.name, files);
		sessionProblems.set(sn.name, probs);
	}

	// --- Scope warnings: sessions modifying >5 files ---
	const scopeWarnings: Array<{
		session_name: string;
		files_modified: number;
		project: string;
		problems_hit: number;
	}> = [];

	for (const sn of sessionNodes) {
		const files = sessionFiles.get(sn.name) ?? [];
		if (files.length > 5) {
			scopeWarnings.push({
				session_name: sn.name,
				files_modified: files.length,
				project: sessionProjects.get(sn.name) ?? "",
				problems_hit: (sessionProblems.get(sn.name) ?? []).length,
			});
		}
	}

	// --- Coupling clusters: file pairs co-modified in 3+ sessions ---
	const pairCounts = new Map<string, number>();
	for (const [, files] of sessionFiles) {
		const sorted = [...new Set(files)].sort();
		for (let i = 0; i < sorted.length; i++) {
			for (let j = i + 1; j < sorted.length; j++) {
				const key = `${sorted[i]}||${sorted[j]}`;
				pairCounts.set(key, (pairCounts.get(key) ?? 0) + 1);
			}
		}
	}

	const couplingClusters: Array<{
		files: string[];
		co_modification_count: number;
		description: string;
	}> = [];

	for (const [key, count] of pairCounts) {
		if (count >= 3) {
			const [fileA, fileB] = key.split("||");
			if (fileA && fileB) {
				couplingClusters.push({
					files: [fileA, fileB],
					co_modification_count: count,
					description: "",
				});
			}
		}
	}
	couplingClusters.sort((a, b) => b.co_modification_count - a.co_modification_count);

	// --- Error hotspots: files most associated with problems ---
	// Re-compute file->problem associations using edges
	const fileProblems = new Map<string, Set<string>>();
	for (const sn of sessionNodes) {
		const sKey = nodeKey(sn);
		const allEdges = [...(outEdges.get(sKey) ?? []), ...(inEdges.get(sKey) ?? [])];
		const filesInSession: string[] = [];
		const problemsInSession: string[] = [];

		for (const e of allEdges) {
			const otherKey = e.source_key === sKey ? e.target_key : e.source_key;
			const other = keyToNode.get(otherKey);
			if (!other) continue;
			if (other.node_type === "file" && e.edge_type === "modifies") {
				filesInSession.push(other.name);
			}
			if (other.node_type === "problem") {
				problemsInSession.push(other.name);
			}
		}

		// Associate each file with each problem in the same session
		for (const f of filesInSession) {
			const set = fileProblems.get(f) ?? new Set<string>();
			for (const p of problemsInSession) {
				set.add(p);
			}
			fileProblems.set(f, set);
		}
	}

	const errorHotspots: Array<{
		file: string;
		problem_count: number;
		recent_problems: string[];
	}> = [];

	for (const [file, problems] of fileProblems) {
		if (problems.size > 0) {
			errorHotspots.push({
				file,
				problem_count: problems.size,
				recent_problems: [...problems].slice(0, 5),
			});
		}
	}
	errorHotspots.sort((a, b) => b.problem_count - a.problem_count);

	// --- Recurring problems: problem patterns in 2+ sessions ---
	const problemSessions = new Map<string, Set<string>>();
	for (const [sessionName, probs] of sessionProblems) {
		for (const p of probs) {
			const set = problemSessions.get(p) ?? new Set<string>();
			set.add(sessionName);
			problemSessions.set(p, set);
		}
	}

	const recurringProblems: Array<{
		pattern: string;
		occurrence_count: number;
		sessions: string[];
	}> = [];

	for (const [pattern, sessions] of problemSessions) {
		if (sessions.size >= 2) {
			recurringProblems.push({
				pattern,
				occurrence_count: sessions.size,
				sessions: [...sessions],
			});
		}
	}
	recurringProblems.sort((a, b) => b.occurrence_count - a.occurrence_count);

	// Stats
	const totalFiles = [...sessionFiles.values()].reduce((sum, f) => sum + f.length, 0);
	const totalProblems = [...sessionProblems.values()].reduce((sum, p) => sum + p.length, 0);

	return c.json({
		date: new Date().toISOString().slice(0, 10),
		coupling_clusters: couplingClusters,
		error_hotspots: errorHotspots.slice(0, 15),
		scope_warnings: scopeWarnings,
		recurring_problems: recurringProblems,
		session_count: sessionNodes.length,
		avg_files_per_session:
			sessionNodes.length > 0
				? Math.round((totalFiles / sessionNodes.length) * 10) / 10
				: 0,
		total_problems: totalProblems,
	});
});

// GET /api/graph/briefing — executive briefing
app.get("/api/graph/briefing", async (c) => {
	const { OUTPUT_DIR } = getConfig();
	const briefingPath = join(OUTPUT_DIR, ".distill-briefing.json");
	try {
		const raw = await Bun.file(briefingPath).text();
		const data = JSON.parse(raw);
		return c.json(data);
	} catch {
		return c.json(
			{
				date: "",
				generated_at: "",
				time_window_hours: 48,
				summary: "",
				areas: [],
				learning: [],
				risks: [],
				recommendations: [],
			},
			200,
		);
	}
});

export default app;
