import { useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";
import type {
	GraphAboutResponse,
	GraphActivityResponse,
	GraphInsightsResponse,
	GraphNodesResponse,
} from "../../shared/schemas.js";

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

type Tab = "briefing" | "activity" | "explorer";
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

	const statusBadge = (s: string) =>
		({
			active: "text-emerald-700 bg-emerald-100 border-emerald-300",
			cooling: "text-amber-700 bg-amber-100 border-amber-300",
			emerging: "text-blue-700 bg-blue-100 border-blue-300",
		})[s] ?? "text-zinc-600 bg-zinc-100 border-zinc-300";

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
// Explorer Tab
// ---------------------------------------------------------------------------

const NODE_COLORS: Record<string, string> = {
	session: "#6366f1",
	project: "#a855f7",
	file: "#22c55e",
	problem: "#ef4444",
	entity: "#f97316",
	goal: "#eab308",
	thread: "#06b6d4",
	decision: "#8b5cf6",
	insight: "#14b8a6",
	artifact: "#64748b",
};

const ALL_NODE_TYPES = Object.keys(NODE_COLORS);

interface ForceNode {
	id: string;
	name: string;
	type: string;
	color: string;
	val: number;
	x?: number;
	y?: number;
}

interface ForceLink {
	source: string | ForceNode;
	target: string | ForceNode;
	type: string;
	weight: number;
}

function ExplorerTab({ hours }: { hours: number }) {
	// biome-ignore lint/suspicious/noExplicitAny: react-force-graph-2d ref type is not well-typed
	const graphRef = useRef<any>(null);
	const containerRef = useRef<HTMLDivElement>(null);
	const [selectedNode, setSelectedNode] = useState<GraphAboutResponse | null>(null);
	const [searchQuery, setSearchQuery] = useState("");
	const [highlightedId, setHighlightedId] = useState<string | null>(null);
	const [hiddenTypes, setHiddenTypes] = useState<Set<string>>(new Set());
	const [containerSize, setContainerSize] = useState({ width: 900, height: 600 });

	// Responsive sizing — fill available space
	useEffect(() => {
		const measure = () => {
			if (containerRef.current) {
				const rect = containerRef.current.getBoundingClientRect();
				const sidebarWidth = selectedNode?.focus ? 320 : 0;
				setContainerSize({
					width: Math.max(rect.width - sidebarWidth, 400),
					height: Math.max(window.innerHeight - rect.top - 32, 500),
				});
			}
		};
		measure();
		window.addEventListener("resize", measure);
		return () => window.removeEventListener("resize", measure);
	}, [selectedNode]);

	const { data, isLoading } = useQuery<GraphNodesResponse>({
		queryKey: ["graph-nodes", hours],
		queryFn: async () => {
			const res = await fetch(`/api/graph/nodes?hours=${hours}`);
			if (!res.ok) throw new Error("Failed to load nodes");
			return res.json();
		},
	});

	// Count nodes per type for the legend
	const typeCounts = useMemo(() => {
		const counts: Record<string, number> = {};
		for (const n of data?.nodes ?? []) {
			counts[n.node_type] = (counts[n.node_type] ?? 0) + 1;
		}
		return counts;
	}, [data]);

	const graphData = useMemo(() => {
		if (!data) return { nodes: [], links: [] };

		const nodes: ForceNode[] = [];
		const nodeKeys = new Set<string>();

		for (const n of data.nodes ?? []) {
			if (hiddenTypes.has(n.node_type)) continue;
			const key = `${n.node_type}:${n.name}`;
			nodeKeys.add(key);
			nodes.push({
				id: key,
				name: n.name,
				type: n.node_type,
				color: NODE_COLORS[n.node_type] ?? "#94a3b8",
				val: n.node_type === "session" ? 3 : n.node_type === "project" ? 5 : 1,
			});
		}

		const links: ForceLink[] = [];
		for (const e of data.edges ?? []) {
			if (nodeKeys.has(e.source_key) && nodeKeys.has(e.target_key)) {
				links.push({
					source: e.source_key,
					target: e.target_key,
					type: e.edge_type,
					weight: e.weight,
				});
			}
		}

		return { nodes, links };
	}, [data, hiddenTypes]);

	// Zoom to fit after data loads
	useEffect(() => {
		if (graphData.nodes.length > 0 && graphRef.current) {
			setTimeout(() => {
				graphRef.current?.zoomToFit(400, 60);
			}, 500);
		}
	}, [graphData.nodes.length]);

	const handleNodeClick = useCallback(
		// biome-ignore lint/suspicious/noExplicitAny: node type is loose from ForceGraph2D
		async (node: any) => {
			const name = node.name as string | undefined;
			if (!name) return;
			setHighlightedId(node.id as string);
			try {
				const res = await fetch(`/api/graph/about/${encodeURIComponent(name)}`);
				if (!res.ok) return;
				const about: GraphAboutResponse = await res.json();
				setSelectedNode(about);
			} catch {
				// ignore fetch errors
			}
		},
		[],
	);

	const nodeCanvasObject = useCallback(
		// biome-ignore lint/suspicious/noExplicitAny: node and ctx types loose from ForceGraph2D
		(node: any, ctx: any, globalScale: number) => {
			const x = node.x as number | undefined;
			const y = node.y as number | undefined;
			const color = (node.color as string | undefined) ?? "#94a3b8";
			const name = (node.name as string | undefined) ?? "";
			const nodeId = (node.id as string | undefined) ?? "";
			const isHighlighted = nodeId === highlightedId;
			const isSearchMatch =
				searchQuery.length > 1 && name.toLowerCase().includes(searchQuery.toLowerCase());

			if (x == null || y == null) return;

			const baseRadius = node.type === "project" ? 6 : node.type === "session" ? 5 : 3.5;
			const radius = isHighlighted ? baseRadius + 3 : isSearchMatch ? baseRadius + 2 : baseRadius;

			// Highlight ring for selected / search match
			if (isHighlighted || isSearchMatch) {
				ctx.beginPath();
				ctx.arc(x, y, radius + 2, 0, 2 * Math.PI, false);
				ctx.strokeStyle = isHighlighted ? "#4f46e5" : "#f59e0b";
				ctx.lineWidth = 2;
				ctx.stroke();
			}

			// Node circle
			ctx.beginPath();
			ctx.arc(x, y, radius, 0, 2 * Math.PI, false);
			ctx.fillStyle = isSearchMatch && !isHighlighted ? "#fbbf24" : color;
			ctx.fill();

			// Label — show at lower zoom for important nodes, always for highlighted
			const showLabel =
				isHighlighted ||
				isSearchMatch ||
				globalScale > 1.2 ||
				(globalScale > 0.6 && (node.type === "project" || node.type === "session"));

			if (showLabel) {
				const fontSize = isHighlighted
					? Math.max(12 / globalScale, 10)
					: Math.round(10 / globalScale);
				ctx.font = `${isHighlighted ? "bold " : ""}${fontSize}px sans-serif`;
				ctx.textAlign = "center";
				ctx.textBaseline = "top";
				ctx.fillStyle = isHighlighted ? "#1e1b4b" : "#374151";
				ctx.fillText(name, x, y + radius + 2);
			}
		},
		[highlightedId, searchQuery],
	);

	const handleSearch = useCallback(() => {
		if (!searchQuery.trim() || !graphRef.current) return;
		const q = searchQuery.trim().toLowerCase();
		const match = graphData.nodes.find((n) => n.name.toLowerCase().includes(q));
		if (match && match.x != null && match.y != null) {
			setHighlightedId(match.id);
			graphRef.current.centerAt(match.x, match.y, 600);
			graphRef.current.zoom(4, 600);
			// Fetch detail for the found node
			fetch(`/api/graph/about/${encodeURIComponent(match.name)}`)
				.then((res) => (res.ok ? res.json() : null))
				.then((about) => {
					if (about) setSelectedNode(about);
				})
				.catch(() => {});
		}
	}, [searchQuery, graphData.nodes]);

	const toggleType = useCallback((type: string) => {
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

	const presentTypes = useMemo(() => {
		if (!data) return [];
		const types = new Set<string>();
		for (const n of data.nodes ?? []) {
			types.add(n.node_type);
		}
		return ALL_NODE_TYPES.filter((t) => types.has(t));
	}, [data]);

	if (isLoading) return <div className="animate-pulse text-zinc-400">Loading graph...</div>;

	const totalNodes = graphData.nodes.length;
	const totalEdges = graphData.links.length;

	return (
		<div ref={containerRef} className="flex flex-col" style={{ minHeight: "calc(100vh - 200px)" }}>
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
						placeholder="Search nodes..."
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
								setSelectedNode(null);
								setSearchQuery("");
								graphRef.current?.zoomToFit(400, 60);
							}}
							className="rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-600 hover:bg-zinc-50"
						>
							Clear
						</button>
					)}
				</div>
				<div className="flex items-center gap-3 text-xs text-zinc-500">
					<span className="font-medium">{totalNodes.toLocaleString()} nodes</span>
					<span className="text-zinc-300">|</span>
					<span className="font-medium">{totalEdges.toLocaleString()} edges</span>
				</div>
			</div>

			{/* Main: sidebar legend + graph + detail panel */}
			<div className="flex flex-1 gap-0 rounded-lg border border-zinc-200 bg-white shadow-sm overflow-hidden">
				{/* Left sidebar — legend & filters */}
				<div className="w-44 shrink-0 border-r border-zinc-200 bg-zinc-50 p-3 overflow-y-auto">
					<h4 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-2">
						Node Types
					</h4>
					<div className="space-y-1">
						{presentTypes.map((type) => {
							const count = typeCounts[type] ?? 0;
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
										style={{
											backgroundColor: NODE_COLORS[type] ?? "#94a3b8",
											opacity: hidden ? 0.3 : 1,
										}}
									/>
									<span className="text-zinc-700 capitalize flex-1">{type}</span>
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
							onClick={() => {
								graphRef.current?.zoomToFit(400, 60);
							}}
							className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-2 py-1.5 text-xs text-zinc-600 hover:bg-zinc-50"
						>
							Fit to view
						</button>
					</div>
				</div>

				{/* Graph canvas */}
				<div className="flex-1 relative bg-zinc-50/30">
					{graphData.nodes.length > 0 ? (
						<ForceGraph2D
							ref={graphRef}
							graphData={graphData}
							nodeLabel="name"
							nodeColor="color"
							nodeVal="val"
							linkDirectionalArrowLength={3}
							linkDirectionalArrowRelPos={1}
							linkWidth={(link: ForceLink) => Math.max(Math.min(link.weight, 4), 0.5)}
							linkColor={() => "#d1d5db"}
							onNodeClick={handleNodeClick}
							nodeCanvasObject={nodeCanvasObject}
							backgroundColor="#fafafa"
							width={containerSize.width - 176 - (selectedNode?.focus ? 0 : 0)}
							height={containerSize.height}
							cooldownTicks={100}
							d3AlphaDecay={0.02}
							d3VelocityDecay={0.3}
						/>
					) : (
						<div className="flex h-full items-center justify-center text-sm text-zinc-400">
							No nodes in this time window. Try expanding to 7d or 30d.
						</div>
					)}
				</div>

				{/* Right detail panel */}
				{selectedNode?.focus && (
					<div className="w-80 shrink-0 border-l border-zinc-200 bg-white p-4 overflow-y-auto">
						<div className="flex items-center justify-between mb-3">
							<div className="flex items-center gap-2">
								<span
									className="inline-block h-3 w-3 rounded-full"
									style={{
										backgroundColor:
											NODE_COLORS[selectedNode.focus.type] ?? "#94a3b8",
									}}
								/>
								<span className="text-xs font-semibold uppercase text-zinc-500">
									{selectedNode.focus.type}
								</span>
							</div>
							<button
								type="button"
								onClick={() => {
									setSelectedNode(null);
									setHighlightedId(null);
								}}
								className="text-zinc-400 hover:text-zinc-600 text-lg leading-none"
							>
								&times;
							</button>
						</div>
						<h4 className="text-lg font-semibold text-zinc-900 mb-2">
							{selectedNode.focus.name}
						</h4>
						{selectedNode.focus.summary && (
							<p className="text-sm text-zinc-600 leading-relaxed mb-4">
								{selectedNode.focus.summary}
							</p>
						)}
						{(selectedNode.neighbors ?? []).length > 0 && (
							<div>
								<h5 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-2">
									Connections ({(selectedNode.neighbors ?? []).length})
								</h5>
								<div className="space-y-1 max-h-96 overflow-y-auto">
									{(selectedNode.neighbors ?? []).slice(0, 30).map((nb) => (
										<div
											key={`${nb.type}:${nb.name}`}
											className="flex items-center gap-2 rounded-md px-2 py-1.5 text-xs hover:bg-zinc-50 cursor-default"
										>
											<span
												className="inline-block h-2.5 w-2.5 rounded-full shrink-0"
												style={{
													backgroundColor: NODE_COLORS[nb.type] ?? "#94a3b8",
												}}
											/>
											<span className="text-zinc-800 truncate flex-1">
												{nb.name}
											</span>
											<span className="text-zinc-400 shrink-0">{nb.type}</span>
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
// Insights Tab
// ---------------------------------------------------------------------------

function InsightSection({
	title,
	subtitle,
	icon,
	count,
	children,
}: {
	title: string;
	subtitle: string;
	icon: string;
	count: number;
	children: React.ReactNode;
}) {
	if (count === 0) return null;
	return (
		<section>
			<div className="mb-2 flex items-center gap-2">
				<span>{icon}</span>
				<h3 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">{title}</h3>
				<span className="text-xs text-zinc-400">({count})</span>
			</div>
			<p className="mb-3 text-xs text-zinc-500">{subtitle}</p>
			<div className="space-y-2">{children}</div>
		</section>
	);
}

function InsightsTab({ hours }: { hours: number }) {
	const { data, isLoading } = useQuery<GraphInsightsResponse>({
		queryKey: ["graph-insights", hours],
		queryFn: async () => {
			const res = await fetch(`/api/graph/insights?hours=${hours}`);
			if (!res.ok) throw new Error("Failed to load insights");
			return res.json();
		},
	});

	if (isLoading) return <div className="animate-pulse text-zinc-400">Loading insights...</div>;
	if (!data) return null;

	const scopeWarnings = data.scope_warnings ?? [];
	const errorHotspots = data.error_hotspots ?? [];
	const couplingClusters = data.coupling_clusters ?? [];
	const recurringProblems = data.recurring_problems ?? [];

	const hasAny =
		scopeWarnings.length > 0 ||
		errorHotspots.length > 0 ||
		couplingClusters.length > 0 ||
		recurringProblems.length > 0;

	return (
		<div className="space-y-6">
			{/* Stats strip */}
			<div className="grid grid-cols-3 gap-3">
				<StatCard label="Sessions" value={data.session_count} />
				<StatCard label="Avg files / session" value={data.avg_files_per_session} />
				<StatCard label="Total problems" value={data.total_problems} />
			</div>

			{!hasAny && (
				<p className="text-sm text-zinc-500">
					No patterns detected in this time window. Try expanding to 7d or 30d.
				</p>
			)}

			{/* Scope Warnings */}
			<InsightSection
				title="Scope Warnings"
				subtitle="Sessions touching many files at once"
				icon="!"
				count={scopeWarnings.length}
			>
				{scopeWarnings.map((w) => (
					<div
						key={w.session_name}
						className="rounded-lg border border-amber-200 bg-amber-50 p-3 dark:border-amber-800 dark:bg-amber-950"
					>
						<p className="truncate text-sm font-medium text-amber-800 dark:text-amber-200">
							{w.session_name}
						</p>
						<div className="mt-1 flex flex-wrap gap-2 text-xs text-amber-700 dark:text-amber-300">
							{w.project && <span>{w.project}</span>}
							<span>{w.files_modified} files modified</span>
							{w.problems_hit > 0 && <span>{w.problems_hit} problems</span>}
						</div>
					</div>
				))}
			</InsightSection>

			{/* Error Hotspots */}
			<InsightSection
				title="Error Hotspots"
				subtitle="Files most associated with problems"
				icon="!"
				count={errorHotspots.length}
			>
				{errorHotspots.map((h) => (
					<div
						key={h.file}
						className="rounded-lg border border-red-200 bg-red-50 p-3 dark:border-red-800 dark:bg-red-950"
					>
						<p className="truncate font-mono text-sm text-red-800 dark:text-red-200">{h.file}</p>
						<p className="mt-1 text-xs text-red-600 dark:text-red-400">
							{h.problem_count} problem{h.problem_count !== 1 ? "s" : ""}
						</p>
					</div>
				))}
			</InsightSection>

			{/* Coupling Clusters */}
			<InsightSection
				title="Coupling Clusters"
				subtitle="Files frequently modified together"
				icon="!"
				count={couplingClusters.length}
			>
				{couplingClusters.map((cl) => {
					const key = (cl.files ?? []).join("||");
					return (
						<div
							key={key}
							className="rounded-lg border border-blue-200 bg-blue-50 p-3 dark:border-blue-800 dark:bg-blue-950"
						>
							<div className="space-y-0.5">
								{(cl.files ?? []).map((f) => (
									<p key={f} className="truncate font-mono text-sm text-blue-800 dark:text-blue-200">
										{f}
									</p>
								))}
							</div>
							<p className="mt-1 text-xs text-blue-600 dark:text-blue-400">
								{cl.co_modification_count} co-modifications
							</p>
						</div>
					);
				})}
			</InsightSection>

			{/* Recurring Problems */}
			<InsightSection
				title="Recurring Problems"
				subtitle="Errors seen across multiple sessions"
				icon="!"
				count={recurringProblems.length}
			>
				{recurringProblems.map((rp) => (
					<div
						key={rp.pattern}
						className="rounded-lg border border-zinc-200 bg-zinc-50 p-3 dark:border-zinc-700 dark:bg-zinc-800"
					>
						<p className="text-sm text-zinc-800 dark:text-zinc-200">{rp.pattern}</p>
						<p className="mt-1 text-xs text-zinc-500">
							{rp.occurrence_count} occurrences across {(rp.sessions ?? []).length} sessions
						</p>
					</div>
				))}
			</InsightSection>
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
		<div className={`mx-auto p-4 md:p-6 ${activeTab === "explorer" ? "" : "max-w-5xl"}`}>
			<div className="space-y-6">
				<h2 className="text-2xl font-bold">Knowledge Graph</h2>

				{/* Time window toggle — only for data tabs, not the pre-computed briefing */}
				{activeTab !== "briefing" && (
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
						{(["briefing", "activity", "explorer"] as const).map((tab) => (
							<button
								key={tab}
								type="button"
								onClick={() => setActiveTab(tab)}
								className={`border-b-2 px-1 pb-2 text-sm font-medium capitalize transition-colors ${
									activeTab === tab
										? "border-indigo-600 text-indigo-600 dark:border-indigo-400 dark:text-indigo-400"
										: "border-transparent text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300"
								}`}
							>
								{tab}
							</button>
						))}
					</nav>
				</div>

				{/* Tab content */}
				{activeTab === "briefing" && <BriefingTab />}
				{activeTab === "activity" && <ActivityTab hours={hours} />}
				{activeTab === "explorer" && <ExplorerTab hours={hours} />}
			</div>
		</div>
	);
}
