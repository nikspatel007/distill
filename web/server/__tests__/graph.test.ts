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
			first_seen: new Date(Date.now() - 3600000).toISOString(),
			last_seen: new Date(Date.now() - 3600000).toISOString(),
		},
		{
			id: "p1",
			node_type: "project",
			name: "distill",
			properties: {},
			first_seen: new Date(Date.now() - 86400000).toISOString(),
			last_seen: new Date(Date.now() - 3600000).toISOString(),
		},
		{
			id: "f1",
			node_type: "file",
			name: "src/graph/store.py",
			properties: {},
			first_seen: new Date(Date.now() - 3600000).toISOString(),
			last_seen: new Date(Date.now() - 3600000).toISOString(),
		},
		{
			id: "f2",
			node_type: "file",
			name: "src/graph/query.py",
			properties: {},
			first_seen: new Date(Date.now() - 3600000).toISOString(),
			last_seen: new Date(Date.now() - 3600000).toISOString(),
		},
		{
			id: "pr1",
			node_type: "problem",
			name: "TypeError: cannot read property",
			properties: { command: "pytest", resolved: true },
			first_seen: new Date(Date.now() - 3600000).toISOString(),
			last_seen: new Date(Date.now() - 3600000).toISOString(),
		},
		{
			id: "e1",
			node_type: "entity",
			name: "pytest",
			properties: {},
			first_seen: new Date(Date.now() - 3600000).toISOString(),
			last_seen: new Date(Date.now() - 3600000).toISOString(),
		},
		{
			id: "g1",
			node_type: "goal",
			name: "Fix failing graph store tests",
			properties: {},
			first_seen: new Date(Date.now() - 3600000).toISOString(),
			last_seen: new Date(Date.now() - 3600000).toISOString(),
		},
	],
	edges: [
		{
			id: "e-1",
			source_key: "session:session-abc",
			target_key: "project:distill",
			edge_type: "executes_in",
			weight: 1,
			properties: {},
		},
		{
			id: "e-2",
			source_key: "session:session-abc",
			target_key: "file:src/graph/store.py",
			edge_type: "modifies",
			weight: 3,
			properties: {},
		},
		{
			id: "e-3",
			source_key: "session:session-abc",
			target_key: "file:src/graph/query.py",
			edge_type: "modifies",
			weight: 1,
			properties: {},
		},
		{
			id: "e-4",
			source_key: "session:session-abc",
			target_key: "problem:TypeError: cannot read property",
			edge_type: "produces",
			weight: 1,
			properties: {},
		},
		{
			id: "e-5",
			source_key: "session:session-abc",
			target_key: "entity:pytest",
			edge_type: "uses",
			weight: 1,
			properties: {},
		},
		{
			id: "e-6",
			source_key: "session:session-abc",
			target_key: "goal:Fix failing graph store tests",
			edge_type: "motivated_by",
			weight: 1,
			properties: {},
		},
	],
};

describe("Graph API", () => {
	beforeEach(async () => {
		await mkdir(TMP_DIR, { recursive: true });
		await writeFile(
			join(TMP_DIR, ".distill-graph.json"),
			JSON.stringify(SAMPLE_GRAPH),
			"utf-8",
		);
		setConfig({
			OUTPUT_DIR: TMP_DIR,
			PORT: 6109,
			PROJECT_DIR: "",
			POSTIZ_URL: "",
			POSTIZ_API_KEY: "",
		});
	});

	afterAll(async () => {
		resetConfig();
		await rm(TMP_DIR, { recursive: true, force: true });
	});

	// --- GET /api/graph/stats ---

	test("GET /api/graph/stats returns correct counts", async () => {
		const res = await app.request("/api/graph/stats");
		expect(res.status).toBe(200);
		const data = await res.json();
		expect(data.total_nodes).toBe(7);
		expect(data.total_edges).toBe(6);
		expect(data.nodes_by_type.session).toBe(1);
		expect(data.nodes_by_type.project).toBe(1);
		expect(data.nodes_by_type.file).toBe(2);
		expect(data.nodes_by_type.problem).toBe(1);
		expect(data.nodes_by_type.entity).toBe(1);
		expect(data.nodes_by_type.goal).toBe(1);
		expect(data.edges_by_type.executes_in).toBe(1);
		expect(data.edges_by_type.modifies).toBe(2);
		expect(data.edges_by_type.produces).toBe(1);
		expect(data.edges_by_type.uses).toBe(1);
		expect(data.edges_by_type.motivated_by).toBe(1);
	});

	test("GET /api/graph/stats handles missing graph file", async () => {
		// Write config pointing to an empty dir (no .distill-graph.json)
		const emptyDir = join(TMP_DIR, "_empty");
		await mkdir(emptyDir, { recursive: true });
		setConfig({
			OUTPUT_DIR: emptyDir,
			PORT: 6109,
			PROJECT_DIR: "",
			POSTIZ_URL: "",
			POSTIZ_API_KEY: "",
		});

		const res = await app.request("/api/graph/stats");
		expect(res.status).toBe(200);
		const data = await res.json();
		expect(data.total_nodes).toBe(0);
		expect(data.total_edges).toBe(0);
	});

	// --- GET /api/graph/about/:name ---

	test("GET /api/graph/about/distill returns focus with neighbors", async () => {
		const res = await app.request("/api/graph/about/distill");
		expect(res.status).toBe(200);
		const data = await res.json();
		expect(data.focus).not.toBeNull();
		expect(data.focus.name).toBe("distill");
		expect(data.focus.type).toBe("project");
		expect(data.neighbors.length).toBeGreaterThan(0);
		// The session is connected to the project via executes_in
		const sessionNeighbor = data.neighbors.find(
			(n: { name: string }) => n.name === "session-abc",
		);
		expect(sessionNeighbor).toBeDefined();
		expect(sessionNeighbor.type).toBe("session");
		expect(data.edges.length).toBeGreaterThan(0);
	});

	test("GET /api/graph/about/nonexistent returns null focus", async () => {
		const res = await app.request("/api/graph/about/nonexistent");
		expect(res.status).toBe(200);
		const data = await res.json();
		expect(data.focus).toBeNull();
		expect(data.neighbors).toHaveLength(0);
		expect(data.edges).toHaveLength(0);
	});

	// --- GET /api/graph/activity ---

	test("GET /api/graph/activity?hours=48 returns sessions", async () => {
		const res = await app.request("/api/graph/activity?hours=48");
		expect(res.status).toBe(200);
		const data = await res.json();
		expect(data.time_window_hours).toBe(48);
		expect(data.sessions).toHaveLength(1);

		const session = data.sessions[0];
		expect(session.project).toBe("distill");
		expect(session.files_modified).toContain("src/graph/store.py");
		expect(session.files_modified).toContain("src/graph/query.py");
		expect(session.entities).toContain("pytest");
		expect(session.problems).toHaveLength(1);
		expect(session.problems[0].error).toBe(
			"TypeError: cannot read property",
		);
		expect(session.problems[0].resolved).toBe(true);
		expect(session.goal).toBe("Fix failing graph store tests");
	});

	// --- GET /api/graph/nodes ---

	test("GET /api/graph/nodes?hours=48 returns active nodes and edges", async () => {
		const res = await app.request("/api/graph/nodes?hours=48");
		expect(res.status).toBe(200);
		const data = await res.json();
		expect(data.nodes.length).toBeGreaterThan(0);
		expect(data.edges.length).toBeGreaterThan(0);
		// All 7 nodes were seen within the last hour, well within 48h
		expect(data.nodes).toHaveLength(7);
		// All 6 edges connect nodes in the active set
		expect(data.edges).toHaveLength(6);
	});

	// --- GET /api/graph/insights ---

	test("GET /api/graph/insights?hours=48 returns all insight categories", async () => {
		const res = await app.request("/api/graph/insights?hours=48");
		expect(res.status).toBe(200);
		const data = await res.json();
		// All 4 insight categories present
		expect(data).toHaveProperty("coupling_clusters");
		expect(data).toHaveProperty("error_hotspots");
		expect(data).toHaveProperty("scope_warnings");
		expect(data).toHaveProperty("recurring_problems");
		// Metadata
		expect(data).toHaveProperty("date");
		expect(data.session_count).toBe(1);
		expect(data.total_problems).toBe(1);
		// With 1 session modifying 2 files + 1 problem,
		// error_hotspots should have entries for those files
		expect(data.error_hotspots.length).toBeGreaterThan(0);
		const hotspot = data.error_hotspots.find(
			(h: { file: string }) => h.file === "src/graph/store.py",
		);
		expect(hotspot).toBeDefined();
		expect(hotspot.recent_problems).toContain(
			"TypeError: cannot read property",
		);
	});

	// --- GET /api/graph/briefing ---

	test("GET /api/graph/briefing returns briefing data or empty default", async () => {
		const res = await app.request("/api/graph/briefing");
		expect(res.status).toBe(200);
		const data = await res.json();
		expect(data).toHaveProperty("summary");
		expect(data).toHaveProperty("areas");
		expect(data).toHaveProperty("learning");
		expect(data).toHaveProperty("risks");
		expect(data).toHaveProperty("recommendations");
	});
});
