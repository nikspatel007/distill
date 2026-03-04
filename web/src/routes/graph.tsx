import { useQuery } from "@tanstack/react-query";
import { useCallback, useMemo, useRef, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";
import type { GraphActivityResponse } from "../../shared/schemas.js";

// ---------------------------------------------------------------------------
// Shared helpers
// ---------------------------------------------------------------------------

function StatCard({ label, value }: { label: string; value: number }) {
	return (
		<div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
			<p className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">{value}</p>
			<p className="text-xs text-zinc-500">{label}</p>
		</div>
	);
}

function relativeTime(hoursAgo: number): string {
	if (hoursAgo < 1) return `${Math.round(hoursAgo * 60)}m ago`;
	if (hoursAgo < 24) return `${Math.round(hoursAgo)}h ago`;
	const days = Math.round(hoursAgo / 24);
	return `${days}d ago`;
}

type Tab = "briefing" | "activity" | "concepts";
type TimeWindow = 24 | 48 | 168 | 720;

const TIME_OPTIONS: { label: string; value: TimeWindow }[] = [
	{ label: "24h", value: 24 },
	{ label: "48h", value: 48 },
	{ label: "7d", value: 168 },
	{ label: "30d", value: 720 },
];

// ---------------------------------------------------------------------------
// Briefing Tab
// ---------------------------------------------------------------------------

function BriefingTab() {
	const { data, isLoading } = useQuery({
		queryKey: ["graph", "briefing"],
		queryFn: async () => {
			const res = await fetch("/api/graph/briefing");
			return res.json();
		},
	});

	if (isLoading) return <div className="animate-pulse text-zinc-400">Loading briefing...</div>;

	if (!data?.summary) {
		return (
			<div className="text-center py-16 text-zinc-500">
				<p className="text-lg">No briefing generated yet</p>
				<p className="text-sm mt-2">
					Run{" "}
					<code className="bg-zinc-800 px-2 py-0.5 rounded">
						distill graph briefing --output ./insights
					</code>{" "}
					to generate one
				</p>
			</div>
		);
	}

	const statusBorder = (s: string) =>
		({
			active: "border-l-emerald-500",
			cooling: "border-l-amber-500",
			emerging: "border-l-blue-500",
		})[s] ?? "border-l-zinc-400";

	const momentumIcon = (m: string) =>
		({ accelerating: "\u2197", steady: "\u2192", decelerating: "\u2198" })[m] ?? "";

	const severityBorder = (s: string) =>
		({
			high: "border-l-red-500",
			medium: "border-l-amber-500",
			low: "border-l-zinc-400",
		})[s] ?? "border-l-zinc-400";

	return (
		<div className="space-y-8">
			{/* Summary */}
			<div className="bg-white border border-zinc-200 rounded-lg p-6 shadow-sm">
				<p className="text-base text-zinc-800 leading-relaxed">{data.summary}</p>
				{data.generated_at && (
					<p className="text-xs text-zinc-400 mt-3">
						Generated {new Date(data.generated_at).toLocaleString()}
					</p>
				)}
			</div>

			{/* Areas */}
			{data.areas?.length > 0 && (
				<section>
					<h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-3">
						Focus Areas
					</h3>
					<div className="grid gap-3 md:grid-cols-2">
						{data.areas.map((area: any, i: number) => (
							<div
								key={i}
								className={`bg-white border border-zinc-200 border-l-4 ${statusBorder(area.status)} rounded-lg p-4 shadow-sm`}
							>
								<div className="flex items-center justify-between mb-1">
									<span className="font-semibold text-zinc-900">{area.name}</span>
									<span
										className={`text-xs font-medium px-2 py-0.5 rounded-full border ${statusBadge(area.status)}`}
									>
										{momentumIcon(area.momentum)} {area.status}
									</span>
								</div>
								<p className="text-sm text-zinc-600 mt-1">{area.headline}</p>
								<div className="flex gap-4 mt-2 text-xs text-zinc-500">
									{area.sessions > 0 && <span>{area.sessions} sessions</span>}
									{area.reading_count > 0 && <span>{area.reading_count} articles</span>}
								</div>
								{area.open_threads?.length > 0 && (
									<div className="mt-3 flex flex-wrap gap-1.5">
										{area.open_threads.map((t: string, j: number) => (
											<span
												key={j}
												className="text-xs text-zinc-600 bg-zinc-100 border border-zinc-200 rounded px-2 py-1"
											>
												{t}
											</span>
										))}
									</div>
								)}
							</div>
						))}
					</div>
				</section>
			)}

			{/* Learning */}
			{data.learning?.length > 0 && (
				<section>
					<h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-3">
						Learning
					</h3>
					<div className="space-y-2">
						{data.learning.map((l: any, i: number) => (
							<div
								key={i}
								className={`bg-white border border-zinc-200 border-l-4 ${statusBorder(l.status)} rounded-lg p-4 shadow-sm`}
							>
								<div className="flex items-center justify-between">
									<span className="font-medium text-zinc-900">{l.topic}</span>
									<span
										className={`text-xs font-medium px-2 py-0.5 rounded-full border ${statusBadge(l.status)}`}
									>
										{l.status}
									</span>
								</div>
								{l.connection && (
									<p className="text-sm text-zinc-600 mt-1">{l.connection}</p>
								)}
								{l.reading_count > 0 && (
									<p className="text-xs text-zinc-500 mt-1">{l.reading_count} articles</p>
								)}
							</div>
						))}
					</div>
				</section>
			)}

			{/* Risks & Recommendations */}
			<div className="grid gap-6 md:grid-cols-2">
				{/* Risks */}
				{data.risks?.length > 0 && (
					<section>
						<h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-3">
							Risks
						</h3>
						<div className="space-y-2">
							{data.risks.map((r: any, i: number) => (
								<div
									key={i}
									className={`bg-white border border-zinc-200 border-l-4 ${severityBorder(r.severity)} rounded-lg p-3 shadow-sm`}
								>
									<div className="flex items-center gap-2">
										<span
											className={`text-xs font-bold uppercase px-1.5 py-0.5 rounded ${
												r.severity === "high"
													? "text-red-700 bg-red-100"
													: r.severity === "medium"
														? "text-amber-700 bg-amber-100"
														: "text-zinc-600 bg-zinc-100"
											}`}
										>
											{r.severity}
										</span>
										<span className="text-sm font-medium text-zinc-800">{r.headline}</span>
									</div>
									{r.detail && (
										<p className="text-sm text-zinc-600 mt-2 leading-relaxed">{r.detail}</p>
									)}
								</div>
							))}
						</div>
					</section>
				)}

				{/* Recommendations */}
				{data.recommendations?.length > 0 && (
					<section>
						<h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-3">
							Recommendations
						</h3>
						<div className="space-y-2">
							{data.recommendations.map((rec: any, i: number) => (
								<div
									key={i}
									className="bg-white border border-zinc-200 border-l-4 border-l-indigo-500 rounded-lg p-3 shadow-sm"
								>
									<div className="flex items-start gap-3">
										<span className="text-lg font-bold text-indigo-600 leading-none mt-0.5">
											{rec.priority}
										</span>
										<div>
											<p className="text-sm font-medium text-zinc-800">{rec.action}</p>
											{rec.rationale && (
												<p className="text-sm text-zinc-600 mt-1 leading-relaxed">
													{rec.rationale}
												</p>
											)}
										</div>
									</div>
								</div>
							))}
						</div>
					</section>
				)}
			</div>
		</div>
	);
}

// ---------------------------------------------------------------------------
// Activity Tab
// ---------------------------------------------------------------------------

function ActivityTab({ hours }: { hours: number }) {
	const { data, isLoading } = useQuery<GraphActivityResponse>({
		queryKey: ["graph-activity", hours],
		queryFn: async () => {
			const res = await fetch(`/api/graph/activity?hours=${hours}`);
			if (!res.ok) throw new Error("Failed to load activity");
			return res.json();
		},
	});

	if (isLoading) return <div className="animate-pulse text-zinc-400">Loading activity...</div>;
	if (!data) return null;

	const stats = data.stats;
	const topEntities = data.top_entities ?? [];
	const sessions = data.sessions ?? [];

	return (
		<div className="space-y-6">
			{/* Stats strip */}
			<div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
				<StatCard label="Sessions" value={stats.session_count} />
				<StatCard label="Files / session" value={stats.avg_files_per_session} />
				<StatCard label="Problems" value={stats.total_problems} />
				<StatCard label="Entities" value={topEntities.length} />
			</div>

			{/* What's on your mind */}
			{topEntities.length > 0 && (
				<section>
					<h3 className="mb-2 text-sm font-semibold text-zinc-700 dark:text-zinc-300">
						What&apos;s on your mind
					</h3>
					<div className="flex flex-wrap gap-2">
						{topEntities.map((e) => (
							<span
								key={e.name}
								className="rounded-full bg-indigo-100 px-3 py-1 text-xs font-medium text-indigo-700 dark:bg-indigo-900 dark:text-indigo-300"
							>
								{e.name}
								<span className="ml-1 opacity-60">{e.count}</span>
							</span>
						))}
					</div>
				</section>
			)}

			{/* Session timeline */}
			{sessions.length > 0 ? (
				<section>
					<h3 className="mb-3 text-sm font-semibold text-zinc-700 dark:text-zinc-300">
						Session timeline
					</h3>
					<div className="relative space-y-4 pl-6">
						{/* Vertical line */}
						<div className="absolute left-2.5 top-1 bottom-1 w-px bg-zinc-200 dark:bg-zinc-700" />

						{sessions.map((s) => (
							<div key={s.id} className="relative">
								{/* Timeline dot */}
								<div className="absolute -left-6 top-1.5 h-3 w-3 rounded-full border-2 border-indigo-500 bg-white dark:bg-zinc-900" />

								<div className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
									<div className="flex flex-wrap items-center gap-2">
										{s.project && (
											<span className="rounded bg-purple-100 px-2 py-0.5 text-xs font-medium text-purple-700 dark:bg-purple-900 dark:text-purple-300">
												{s.project}
											</span>
										)}
										<span className="text-xs text-zinc-400">
											{relativeTime(s.hours_ago)}
										</span>
										{s.problems.length > 0 && (
											<span className="rounded bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700 dark:bg-red-900 dark:text-red-300">
												{s.problems.length} problem{s.problems.length !== 1 ? "s" : ""}
											</span>
										)}
									</div>

									{(s.goal || s.summary) && (
										<p className="mt-1.5 text-sm text-zinc-700 dark:text-zinc-300">
											{s.goal || s.summary}
										</p>
									)}

									{/* File chips */}
									{s.files_modified.length > 0 && (
										<div className="mt-2 flex flex-wrap gap-1">
											{s.files_modified.slice(0, 8).map((f) => (
												<span
													key={f}
													className="rounded bg-green-100 px-1.5 py-0.5 text-xs text-green-700 dark:bg-green-900 dark:text-green-300"
												>
													{f.split("/").pop() ?? f}
												</span>
											))}
											{s.files_modified.length > 8 && (
												<span className="text-xs text-zinc-400">
													+{s.files_modified.length - 8} more
												</span>
											)}
										</div>
									)}

									{/* Entity chips */}
									{s.entities.length > 0 && (
										<div className="mt-1.5 flex flex-wrap gap-1">
											{s.entities.map((e) => (
												<span
													key={e}
													className="rounded bg-blue-100 px-1.5 py-0.5 text-xs text-blue-700 dark:bg-blue-900 dark:text-blue-300"
												>
													{e}
												</span>
											))}
										</div>
									)}
								</div>
							</div>
						))}
					</div>
				</section>
			) : (
				<p className="text-sm text-zinc-500">
					No sessions in this time window. Try expanding to 7d or 30d.
				</p>
			)}
		</div>
	);
}

// ---------------------------------------------------------------------------
// Concept Graph (replaces old Explorer)
// ---------------------------------------------------------------------------

type ConceptNodeType = "project" | "topic" | "thread" | "risk" | "entity";

interface ConceptNode {
	id: string;
	label: string;
	type: ConceptNodeType;
	color: string;
	width: number;
	height: number;
	status?: string;
	detail?: string;
	x?: number;
	y?: number;
}

interface ConceptLink {
	source: string | ConceptNode;
	target: string | ConceptNode;
	label: string;
}

const CONCEPT_COLORS: Record<ConceptNodeType, Record<string, string>> = {
	project: { active: "#22c55e", cooling: "#f59e0b", emerging: "#3b82f6", default: "#22c55e" },
	topic: { active: "#3b82f6", cooling: "#f59e0b", emerging: "#8b5cf6", default: "#3b82f6" },
	thread: { active: "#f97316", cooling: "#a3a3a3", emerging: "#f97316", default: "#f97316" },
	risk: { high: "#ef4444", medium: "#f59e0b", low: "#a3a3a3", default: "#ef4444" },
	entity: { default: "#6b7280" },
};

const CONCEPT_SIZES: Record<ConceptNodeType, { width: number; height: number }> = {
	project: { width: 160, height: 44 },
	topic: { width: 140, height: 36 },
	thread: { width: 130, height: 32 },
	risk: { width: 130, height: 32 },
	entity: { width: 110, height: 28 },
};

const CONCEPT_LEGEND: { type: ConceptNodeType; label: string; color: string }[] = [
	{ type: "project", label: "Projects", color: "#22c55e" },
	{ type: "topic", label: "Topics", color: "#3b82f6" },
	{ type: "thread", label: "Threads", color: "#f97316" },
	{ type: "risk", label: "Risks", color: "#ef4444" },
	{ type: "entity", label: "Entities", color: "#6b7280" },
];

function conceptColor(type: ConceptNodeType, status?: string): string {
	const palette = CONCEPT_COLORS[type];
	return palette[status ?? "default"] ?? palette.default ?? "#6b7280";
}

function truncate(s: string, max: number): string {
	return s.length <= max ? s : `${s.slice(0, max - 1)}\u2026`;
}

function statusBadge(s: string): string {
	return (
		({
			active: "text-emerald-700 bg-emerald-100 border-emerald-300",
			cooling: "text-amber-700 bg-amber-100 border-amber-300",
			emerging: "text-blue-700 bg-blue-100 border-blue-300",
			high: "text-red-700 bg-red-100 border-red-300",
			medium: "text-amber-700 bg-amber-100 border-amber-300",
			low: "text-zinc-600 bg-zinc-100 border-zinc-300",
		})[s] ?? "text-zinc-600 bg-zinc-100 border-zinc-300"
	);
}

// biome-ignore lint/suspicious/noExplicitAny: briefing/activity are untyped JSON
function buildConceptGraph(briefing: any, activity: any): { nodes: ConceptNode[]; links: ConceptLink[] } {
	const nodes: ConceptNode[] = [];
	const links: ConceptLink[] = [];
	const nodeIds = new Set<string>();

	const addNode = (id: string, label: string, type: ConceptNodeType, status?: string, detail?: string) => {
		if (nodeIds.has(id)) return;
		nodeIds.add(id);
		const size = CONCEPT_SIZES[type];
		nodes.push({ id, label: truncate(label, 24), type, color: conceptColor(type, status), width: size.width, height: size.height, status, detail });
	};

	const addLink = (source: string, target: string, label: string) => {
		if (nodeIds.has(source) && nodeIds.has(target) && source !== target) {
			links.push({ source, target, label });
		}
	};

	// 1. Projects from briefing areas
	const areas = briefing?.areas ?? [];
	for (const area of areas) {
		const pid = `project:${area.name}`;
		addNode(pid, area.name, "project", area.status, area.headline);

		// 2. Threads from open_threads (max 3 per project)
		const threads: string[] = area.open_threads ?? [];
		for (const t of threads.slice(0, 3)) {
			const tid = `thread:${t}`;
			addNode(tid, t, "thread", area.status, `Open thread in ${area.name}`);
			addLink(pid, tid, "open thread");
		}
	}

	// 3. Topics from briefing learning
	const learnings = briefing?.learning ?? [];
	for (const l of learnings) {
		const tid = `topic:${l.topic}`;
		addNode(tid, l.topic, "topic", l.status, l.connection);

		// Link to project if area name appears in connection text
		const conn = (l.connection ?? "").toLowerCase();
		for (const area of areas) {
			if (conn.includes(area.name.toLowerCase())) {
				addLink(`project:${area.name}`, tid, "learning");
			}
		}
	}

	// Topic-to-topic edges for same status
	for (let i = 0; i < learnings.length; i++) {
		for (let j = i + 1; j < learnings.length; j++) {
			if (learnings[i].status === learnings[j].status) {
				addLink(`topic:${learnings[i].topic}`, `topic:${learnings[j].topic}`, "related");
			}
		}
	}

	// 4. Risks from briefing risks
	const risks = briefing?.risks ?? [];
	for (const r of risks) {
		const rid = `risk:${r.headline}`;
		addNode(rid, r.headline, "risk", r.severity, r.detail);

		// Link to projects via risk.project field (comma-split)
		const projects = (r.project ?? "").split(",").map((s: string) => s.trim()).filter(Boolean);
		for (const p of projects) {
			if (nodeIds.has(`project:${p}`)) {
				addLink(`project:${p}`, rid, "risk");
			}
		}
		// If no project matched, link to all projects
		if (projects.length === 0) {
			for (const area of areas) {
				addLink(`project:${area.name}`, rid, "risk");
			}
		}
	}

	// 5. Entities from activity top_entities (top 8)
	const entities = (activity?.top_entities ?? []).slice(0, 8);
	for (const e of entities) {
		const eid = `entity:${e.name}`;
		addNode(eid, e.name, "entity", undefined, `Mentioned ${e.count} times`);
	}

	// Link entities to projects via session data
	const sessions = activity?.sessions ?? [];
	const projectEntities: Record<string, Set<string>> = {};
	for (const s of sessions) {
		const proj = s.project;
		if (!proj) continue;
		if (!projectEntities[proj]) projectEntities[proj] = new Set();
		for (const ent of s.entities ?? []) {
			projectEntities[proj].add(ent);
		}
	}
	for (const e of entities) {
		for (const [proj, ents] of Object.entries(projectEntities)) {
			if (ents.has(e.name) && nodeIds.has(`project:${proj}`)) {
				addLink(`project:${proj}`, `entity:${e.name}`, "uses");
			}
		}
	}

	return { nodes, links };
}

function roundedRect(
	ctx: CanvasRenderingContext2D,
	x: number,
	y: number,
	w: number,
	h: number,
	r: number,
) {
	ctx.beginPath();
	ctx.moveTo(x + r, y);
	ctx.lineTo(x + w - r, y);
	ctx.quadraticCurveTo(x + w, y, x + w, y + r);
	ctx.lineTo(x + w, y + h - r);
	ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
	ctx.lineTo(x + r, y + h);
	ctx.quadraticCurveTo(x, y + h, x, y + h - r);
	ctx.lineTo(x, y + r);
	ctx.quadraticCurveTo(x, y, x + r, y);
	ctx.closePath();
}

interface SelectedConcept {
	node: ConceptNode;
	connections: { node: ConceptNode; label: string }[];
}

function ConceptsTab() {
	// biome-ignore lint/suspicious/noExplicitAny: react-force-graph-2d ref type is not well-typed
	const graphRef = useRef<any>(null);
	const [selected, setSelected] = useState<SelectedConcept | null>(null);
	const [searchQuery, setSearchQuery] = useState("");
	const [highlightedId, setHighlightedId] = useState<string | null>(null);
	const [hiddenTypes, setHiddenTypes] = useState<Set<ConceptNodeType>>(new Set());

	// biome-ignore lint/suspicious/noExplicitAny: briefing response is untyped
	const { data: briefing, isLoading: loadingBriefing } = useQuery<any>({
		queryKey: ["graph", "briefing"],
		queryFn: async () => {
			const res = await fetch("/api/graph/briefing");
			return res.json();
		},
	});

	const { data: activity, isLoading: loadingActivity } = useQuery<GraphActivityResponse>({
		queryKey: ["graph-activity", 48],
		queryFn: async () => {
			const res = await fetch("/api/graph/activity?hours=48");
			if (!res.ok) throw new Error("Failed to load activity");
			return res.json();
		},
	});

	const { nodes: allNodes, links: allLinks } = useMemo(
		() => buildConceptGraph(briefing, activity),
		[briefing, activity],
	);

	const typeCounts = useMemo(() => {
		const counts: Record<string, number> = {};
		for (const n of allNodes) {
			counts[n.type] = (counts[n.type] ?? 0) + 1;
		}
		return counts;
	}, [allNodes]);

	const graphData = useMemo(() => {
		const visibleIds = new Set<string>();
		const nodes = allNodes.filter((n) => {
			if (hiddenTypes.has(n.type)) return false;
			visibleIds.add(n.id);
			return true;
		});
		const links = allLinks.filter(
			(l) => {
				const sid = typeof l.source === "string" ? l.source : l.source.id;
				const tid = typeof l.target === "string" ? l.target : l.target.id;
				return visibleIds.has(sid) && visibleIds.has(tid);
			},
		);
		return { nodes, links };
	}, [allNodes, allLinks, hiddenTypes]);

	// Configure forces once the graph ref is available
	const graphRefCallback = useCallback(
		// biome-ignore lint/suspicious/noExplicitAny: react-force-graph-2d ref type is not well-typed
		(fg: any) => {
			if (!fg) return;
			graphRef.current = fg;
			// Strong charge repulsion to spread nodes apart
			const charge = fg.d3Force("charge");
			if (charge?.strength) charge.strength(-600);
			// Wide link distance so connected nodes don't overlap
			const link = fg.d3Force("link");
			if (link?.distance) link.distance(180);
		},
		[],
	);

	const handleNodeClick = useCallback(
		// biome-ignore lint/suspicious/noExplicitAny: node type is loose from ForceGraph2D
		(node: any) => {
			const conceptNode = node as ConceptNode;
			if (!conceptNode.id) return;
			setHighlightedId(conceptNode.id);

			// Build connections from allLinks
			const connections: { node: ConceptNode; label: string }[] = [];
			for (const link of allLinks) {
				const sid = typeof link.source === "string" ? link.source : (link.source as ConceptNode).id;
				const tid = typeof link.target === "string" ? link.target : (link.target as ConceptNode).id;
				if (sid === conceptNode.id) {
					const target = allNodes.find((n) => n.id === tid);
					if (target) connections.push({ node: target, label: link.label });
				} else if (tid === conceptNode.id) {
					const source = allNodes.find((n) => n.id === sid);
					if (source) connections.push({ node: source, label: link.label });
				}
			}
			setSelected({ node: conceptNode, connections });
		},
		[allNodes, allLinks],
	);

	const nodeCanvasObject = useCallback(
		// biome-ignore lint/suspicious/noExplicitAny: node and ctx types loose from ForceGraph2D
		(node: any, ctx: any, globalScale: number) => {
			const n = node as ConceptNode;
			const x = n.x;
			const y = n.y;
			if (x == null || y == null) return;

			// Fixed size in graph coordinates (not screen pixels)
			const w = n.width;
			const h = n.height;
			const isHighlighted = n.id === highlightedId;
			const isSearchMatch =
				searchQuery.length > 1 && n.label.toLowerCase().includes(searchQuery.toLowerCase());

			// Highlight ring
			if (isHighlighted || isSearchMatch) {
				const pad = 4;
				roundedRect(ctx, x - w / 2 - pad, y - h / 2 - pad, w + pad * 2, h + pad * 2, 8);
				ctx.strokeStyle = isHighlighted ? "#4f46e5" : "#f59e0b";
				ctx.lineWidth = 2.5;
				ctx.stroke();
			}

			// Background fill (15% opacity)
			roundedRect(ctx, x - w / 2, y - h / 2, w, h, 6);
			ctx.fillStyle = `${n.color}26`;
			ctx.fill();
			ctx.strokeStyle = n.color;
			ctx.lineWidth = 1.5;
			ctx.stroke();

			// Label
			const fontSize = 11;
			ctx.font = `${n.type === "project" ? "bold " : "600 "}${fontSize}px -apple-system, BlinkMacSystemFont, sans-serif`;
			ctx.textAlign = "center";
			ctx.textBaseline = "middle";
			ctx.fillStyle = "#1f2937";
			ctx.fillText(n.label, x, y);

			// Type badge below node
			if (globalScale > 0.4) {
				const badgeFontSize = 8;
				ctx.font = `500 ${badgeFontSize}px -apple-system, BlinkMacSystemFont, sans-serif`;
				ctx.fillStyle = n.color;
				ctx.fillText(n.type, x, y + h / 2 + badgeFontSize + 2);
			}
		},
		[highlightedId, searchQuery],
	);

	const linkCanvasObject = useCallback(
		// biome-ignore lint/suspicious/noExplicitAny: link and ctx types loose from ForceGraph2D
		(link: any, ctx: any, globalScale: number) => {
			const src = link.source;
			const tgt = link.target;
			if (!src || !tgt || src.x == null || src.y == null || tgt.x == null || tgt.y == null) return;

			ctx.beginPath();
			ctx.moveTo(src.x, src.y);
			ctx.lineTo(tgt.x, tgt.y);
			ctx.strokeStyle = "#d1d5db";
			ctx.lineWidth = 1;
			ctx.stroke();

			// Edge label at midpoint
			if (globalScale > 0.4 && link.label) {
				const mx = (src.x + tgt.x) / 2;
				const my = (src.y + tgt.y) / 2;
				const fontSize = 8;
				ctx.font = `400 ${fontSize}px -apple-system, BlinkMacSystemFont, sans-serif`;
				ctx.textAlign = "center";
				ctx.textBaseline = "middle";
				ctx.fillStyle = "#9ca3af";
				ctx.fillText(link.label, mx, my);
			}
		},
		[],
	);

	const handleSearch = useCallback(() => {
		if (!searchQuery.trim() || !graphRef.current) return;
		const q = searchQuery.trim().toLowerCase();
		const match = graphData.nodes.find((n) => n.label.toLowerCase().includes(q));
		if (match && match.x != null && match.y != null) {
			setHighlightedId(match.id);
			graphRef.current.centerAt(match.x, match.y, 600);
			graphRef.current.zoom(3, 600);
			// Build connections locally
			const connections: { node: ConceptNode; label: string }[] = [];
			for (const link of allLinks) {
				const sid = typeof link.source === "string" ? link.source : (link.source as ConceptNode).id;
				const tid = typeof link.target === "string" ? link.target : (link.target as ConceptNode).id;
				if (sid === match.id) {
					const target = allNodes.find((n) => n.id === tid);
					if (target) connections.push({ node: target, label: link.label });
				} else if (tid === match.id) {
					const source = allNodes.find((n) => n.id === sid);
					if (source) connections.push({ node: source, label: link.label });
				}
			}
			setSelected({ node: match, connections });
		}
	}, [searchQuery, graphData.nodes, allNodes, allLinks]);

	const toggleType = useCallback((type: ConceptNodeType) => {
		setHiddenTypes((prev) => {
			const next = new Set(prev);
			if (next.has(type)) {
				next.delete(type);
			} else {
				next.add(type);
			}
			return next;
		});
	}, []);

	if (loadingBriefing || loadingActivity)
		return <div className="animate-pulse text-zinc-400">Loading concept graph...</div>;

	if (allNodes.length === 0) {
		return (
			<div className="text-center py-16 text-zinc-500">
				<p className="text-lg">No concept data available</p>
				<p className="text-sm mt-2">
					Run{" "}
					<code className="bg-zinc-800 text-zinc-200 px-2 py-0.5 rounded">
						distill graph briefing --output ./insights
					</code>{" "}
					to generate briefing data
				</p>
			</div>
		);
	}

	return (
		<div className="flex flex-col" style={{ height: "calc(100vh - 200px)" }}>
			{/* Top bar: search + stats */}
			<div className="flex items-center justify-between gap-4 mb-3">
				<div className="flex items-center gap-2">
					<input
						type="text"
						value={searchQuery}
						onChange={(e) => setSearchQuery(e.target.value)}
						onKeyDown={(e) => {
							if (e.key === "Enter") handleSearch();
						}}
						placeholder="Search concepts..."
						className="w-64 rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400"
					/>
					<button
						type="button"
						onClick={handleSearch}
						className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-indigo-700"
					>
						Find
					</button>
					{highlightedId && (
						<button
							type="button"
							onClick={() => {
								setHighlightedId(null);
								setSelected(null);
								setSearchQuery("");
								graphRef.current?.zoomToFit(400, 80);
							}}
							className="rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-600 hover:bg-zinc-50"
						>
							Clear
						</button>
					)}
				</div>
				<div className="flex items-center gap-3 text-xs text-zinc-500">
					<span className="font-medium">{graphData.nodes.length} concepts</span>
					<span className="text-zinc-300">|</span>
					<span className="font-medium">{graphData.links.length} connections</span>
				</div>
			</div>

			{/* Main: sidebar legend + graph + detail panel */}
			<div className="flex flex-1 gap-0 rounded-lg border border-zinc-200 bg-white shadow-sm overflow-hidden">
				{/* Left sidebar — legend & filters */}
				<div className="w-44 shrink-0 border-r border-zinc-200 bg-zinc-50 p-3 overflow-y-auto">
					<h4 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-2">
						Concept Types
					</h4>
					<div className="space-y-1">
						{CONCEPT_LEGEND.map(({ type, label, color }) => {
							const count = typeCounts[type] ?? 0;
							if (count === 0) return null;
							const hidden = hiddenTypes.has(type);
							return (
								<button
									key={type}
									type="button"
									onClick={() => toggleType(type)}
									className={`flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-xs transition-colors ${
										hidden
											? "opacity-40 hover:opacity-60"
											: "hover:bg-zinc-200/60"
									}`}
								>
									<span
										className="inline-block h-3 w-3 rounded-full shrink-0"
										style={{ backgroundColor: color, opacity: hidden ? 0.3 : 1 }}
									/>
									<span className="text-zinc-700 flex-1">{label}</span>
									<span className="text-zinc-400 tabular-nums">{count}</span>
								</button>
							);
						})}
					</div>
					<div className="mt-4 pt-3 border-t border-zinc-200">
						<button
							type="button"
							onClick={() => setHiddenTypes(new Set())}
							className="w-full rounded-md border border-zinc-300 bg-white px-2 py-1.5 text-xs text-zinc-600 hover:bg-zinc-50"
						>
							Show all
						</button>
						<button
							type="button"
							onClick={() => graphRef.current?.zoomToFit(400, 80)}
							className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-2 py-1.5 text-xs text-zinc-600 hover:bg-zinc-50"
						>
							Fit to view
						</button>
					</div>
				</div>

				{/* Graph canvas */}
				<div className="flex-1 relative bg-zinc-50/30 min-h-0">
					<ForceGraph2D
						ref={graphRefCallback}
						graphData={graphData}
						nodeLabel=""
						onNodeClick={handleNodeClick}
						onNodeDragEnd={() => {
							// Re-heat simulation slightly after drag
							graphRef.current?.d3ReheatSimulation();
						}}
						nodeCanvasObject={nodeCanvasObject}
						nodeCanvasObjectMode={() => "replace" as const}
						linkCanvasObject={linkCanvasObject}
						linkCanvasObjectMode={() => "replace" as const}
						nodePointerAreaPaint={(node: ConceptNode, color: string, ctx: CanvasRenderingContext2D) => {
							const w = node.width;
							const h = node.height;
							const x = node.x ?? 0;
							const y = node.y ?? 0;
							ctx.fillStyle = color;
							ctx.fillRect(x - w / 2, y - h / 2, w, h);
						}}
						enableNodeDrag={true}
						backgroundColor="#fafafa"
						cooldownTicks={100}
						d3AlphaDecay={0.03}
						d3VelocityDecay={0.25}
						onEngineStop={() => graphRef.current?.zoomToFit(400, 80)}
					/>
				</div>

				{/* Right detail panel */}
				{selected && (
					<div className="w-80 shrink-0 border-l border-zinc-200 bg-white p-4 overflow-y-auto">
						<div className="flex items-center justify-between mb-3">
							<div className="flex items-center gap-2">
								<span
									className="inline-block h-3 w-3 rounded-full"
									style={{ backgroundColor: selected.node.color }}
								/>
								<span className="text-xs font-semibold uppercase text-zinc-500">
									{selected.node.type}
								</span>
								{selected.node.status && (
									<span
										className={`text-xs font-medium px-2 py-0.5 rounded-full border ${statusBadge(selected.node.status)}`}
									>
										{selected.node.status}
									</span>
								)}
							</div>
							<button
								type="button"
								onClick={() => {
									setSelected(null);
									setHighlightedId(null);
								}}
								className="text-zinc-400 hover:text-zinc-600 text-lg leading-none"
							>
								&times;
							</button>
						</div>
						<h4 className="text-lg font-semibold text-zinc-900 mb-2">
							{selected.node.label}
						</h4>
						{selected.node.detail && (
							<p className="text-sm text-zinc-600 leading-relaxed mb-4">
								{selected.node.detail}
							</p>
						)}
						{selected.connections.length > 0 && (
							<div>
								<h5 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-2">
									Connections ({selected.connections.length})
								</h5>
								<div className="space-y-1 max-h-96 overflow-y-auto">
									{selected.connections.map((c) => (
										<div
											key={c.node.id}
											className="flex items-center gap-2 rounded-md px-2 py-1.5 text-xs hover:bg-zinc-50 cursor-default"
										>
											<span
												className="inline-block h-2.5 w-2.5 rounded-full shrink-0"
												style={{ backgroundColor: c.node.color }}
											/>
											<span className="text-zinc-800 truncate flex-1">
												{c.node.label}
											</span>
											<span className="text-zinc-400 shrink-0">{c.label}</span>
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

// ---------------------------------------------------------------------------
// Main Graph Page
// ---------------------------------------------------------------------------

export default function GraphPage() {
	const [hours, setHours] = useState<TimeWindow>(48);
	const [activeTab, setActiveTab] = useState<Tab>("briefing");

	return (
		<div className={`mx-auto p-4 md:p-6 ${activeTab === "concepts" ? "" : "max-w-5xl"}`}>
			<div className="space-y-6">
				<h2 className="text-2xl font-bold">Knowledge Graph</h2>

				{/* Time window toggle — only for data tabs, not the pre-computed briefing */}
				{activeTab === "activity" && (
					<div className="flex items-center gap-2">
						{TIME_OPTIONS.map((opt) => (
							<button
								key={opt.value}
								type="button"
								onClick={() => setHours(opt.value)}
								className={`rounded-full px-3 py-1 text-sm font-medium transition-colors ${
									hours === opt.value
										? "bg-indigo-600 text-white"
										: "bg-zinc-100 text-zinc-600 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-400 dark:hover:bg-zinc-700"
								}`}
							>
								{opt.label}
							</button>
						))}
					</div>
				)}

				{/* Tab bar */}
				<div className="border-b border-zinc-200 dark:border-zinc-800">
					<nav className="-mb-px flex gap-4" aria-label="Graph tabs">
						{[{ key: "briefing" as const, label: "Briefing" }, { key: "activity" as const, label: "Activity" }, { key: "concepts" as const, label: "Concepts" }].map(({ key, label }) => (
							<button
								key={key}
								type="button"
								onClick={() => setActiveTab(key)}
								className={`border-b-2 px-1 pb-2 text-sm font-medium transition-colors ${
									activeTab === key
										? "border-indigo-600 text-indigo-600 dark:border-indigo-400 dark:text-indigo-400"
										: "border-transparent text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300"
								}`}
							>
								{label}
							</button>
						))}
					</nav>
				</div>

				{/* Tab content */}
				{activeTab === "briefing" && <BriefingTab />}
				{activeTab === "activity" && <ActivityTab hours={hours} />}
				{activeTab === "concepts" && <ConceptsTab />}
			</div>
		</div>
	);
}
