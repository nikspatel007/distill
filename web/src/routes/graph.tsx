import { useQuery } from "@tanstack/react-query";
import { useCallback, useMemo, useRef, useState } from "react";
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

type Tab = "activity" | "explorer" | "insights";
type TimeWindow = 24 | 48 | 168 | 720;

const TIME_OPTIONS: { label: string; value: TimeWindow }[] = [
	{ label: "24h", value: 24 },
	{ label: "48h", value: 48 },
	{ label: "7d", value: 168 },
	{ label: "30d", value: 720 },
];

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
	const [selectedNode, setSelectedNode] = useState<GraphAboutResponse | null>(null);
	const [searchQuery, setSearchQuery] = useState("");
	const [hiddenTypes, setHiddenTypes] = useState<Set<string>>(new Set());

	const { data, isLoading } = useQuery<GraphNodesResponse>({
		queryKey: ["graph-nodes", hours],
		queryFn: async () => {
			const res = await fetch(`/api/graph/nodes?hours=${hours}`);
			if (!res.ok) throw new Error("Failed to load nodes");
			return res.json();
		},
	});

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
				val: 1,
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

	const handleNodeClick = useCallback(
		// biome-ignore lint/suspicious/noExplicitAny: node type is loose from ForceGraph2D
		async (node: any) => {
			const name = node.name as string | undefined;
			if (!name) return;
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

			if (x == null || y == null) return;

			// Draw circle
			const radius = 4;
			ctx.beginPath();
			ctx.arc(x, y, radius, 0, 2 * Math.PI, false);
			ctx.fillStyle = color;
			ctx.fill();

			// Draw label when zoomed in
			if (globalScale > 1.5) {
				ctx.font = `${Math.round(10 / globalScale)}px sans-serif`;
				ctx.textAlign = "center";
				ctx.textBaseline = "top";
				ctx.fillStyle = "#374151";
				ctx.fillText(name, x, y + radius + 2);
			}
		},
		[],
	);

	const handleSearch = useCallback(() => {
		if (!searchQuery.trim() || !graphRef.current) return;
		const q = searchQuery.trim().toLowerCase();
		const match = graphData.nodes.find(
			(n) => n.name.toLowerCase().includes(q),
		);
		if (match && match.x != null && match.y != null) {
			graphRef.current.centerAt(match.x, match.y, 400);
			graphRef.current.zoom(3, 400);
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

	if (isLoading) return <div className="animate-pulse text-zinc-400">Loading graph...</div>;

	const presentTypes = useMemo(() => {
		if (!data) return [];
		const types = new Set<string>();
		for (const n of data.nodes ?? []) {
			types.add(n.node_type);
		}
		return ALL_NODE_TYPES.filter((t) => types.has(t));
	}, [data]);

	return (
		<div className="space-y-4">
			{/* Controls row */}
			<div className="flex flex-wrap items-center gap-3">
				<div className="flex gap-2">
					<input
						type="text"
						value={searchQuery}
						onChange={(e) => setSearchQuery(e.target.value)}
						onKeyDown={(e) => {
							if (e.key === "Enter") handleSearch();
						}}
						placeholder="Search nodes..."
						className="rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
					/>
					<button
						type="button"
						onClick={handleSearch}
						className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm text-white hover:bg-indigo-700"
					>
						Find
					</button>
				</div>
				<div className="flex flex-wrap gap-2">
					{presentTypes.map((type) => (
						<label key={type} className="flex items-center gap-1.5 text-xs cursor-pointer">
							<input
								type="checkbox"
								checked={!hiddenTypes.has(type)}
								onChange={() => toggleType(type)}
								className="rounded"
							/>
							<span
								className="inline-block h-2.5 w-2.5 rounded-full"
								style={{ backgroundColor: NODE_COLORS[type] ?? "#94a3b8" }}
							/>
							<span className="text-zinc-600 dark:text-zinc-400">{type}</span>
						</label>
					))}
				</div>
			</div>

			{/* Main area: graph + detail panel */}
			<div className="flex gap-4">
				<div className="flex-1 rounded-lg border border-zinc-200 dark:border-zinc-800" style={{ height: 500 }}>
					{graphData.nodes.length > 0 ? (
						<ForceGraph2D
							ref={graphRef}
							graphData={graphData}
							nodeLabel="name"
							nodeColor="color"
							nodeVal="val"
							linkDirectionalArrowLength={3}
							linkDirectionalArrowRelPos={1}
							linkWidth={(link: ForceLink) => Math.min(link.weight, 5)}
							linkColor={() => "#94a3b8"}
							onNodeClick={handleNodeClick}
							nodeCanvasObject={nodeCanvasObject}
							width={undefined}
							height={500}
						/>
					) : (
						<div className="flex h-full items-center justify-center text-sm text-zinc-400">
							No nodes in this time window. Try expanding to 7d or 30d.
						</div>
					)}
				</div>

				{/* Detail panel */}
				{selectedNode?.focus && (
					<div className="w-72 shrink-0 space-y-3 rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
						<div className="flex items-center gap-2">
							<span
								className="inline-block h-3 w-3 rounded-full"
								style={{ backgroundColor: NODE_COLORS[selectedNode.focus.type] ?? "#94a3b8" }}
							/>
							<span className="text-xs font-medium uppercase text-zinc-500">
								{selectedNode.focus.type}
							</span>
						</div>
						<h4 className="font-semibold text-zinc-900 dark:text-zinc-100">
							{selectedNode.focus.name}
						</h4>
						{selectedNode.focus.summary && (
							<p className="text-sm text-zinc-600 dark:text-zinc-400">
								{selectedNode.focus.summary}
							</p>
						)}
						{(selectedNode.neighbors ?? []).length > 0 && (
							<div>
								<h5 className="mb-1 text-xs font-medium text-zinc-500">Neighbors</h5>
								<ul className="space-y-1">
									{(selectedNode.neighbors ?? []).slice(0, 20).map((nb) => (
										<li key={`${nb.type}:${nb.name}`} className="flex items-center gap-1.5 text-xs">
											<span
												className="inline-block h-2 w-2 rounded-full"
												style={{ backgroundColor: NODE_COLORS[nb.type] ?? "#94a3b8" }}
											/>
											<span className="text-zinc-700 dark:text-zinc-300">{nb.name}</span>
											<span className="text-zinc-400">({nb.type})</span>
										</li>
									))}
								</ul>
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
	const [activeTab, setActiveTab] = useState<Tab>("activity");

	return (
		<div className="mx-auto max-w-5xl p-4 md:p-6">
			<div className="space-y-6">
				<h2 className="text-2xl font-bold">Knowledge Graph</h2>

				{/* Time window toggle */}
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

				{/* Tab bar */}
				<div className="border-b border-zinc-200 dark:border-zinc-800">
					<nav className="-mb-px flex gap-4" aria-label="Graph tabs">
						{(["activity", "explorer", "insights"] as const).map((tab) => (
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
				{activeTab === "activity" && <ActivityTab hours={hours} />}
				{activeTab === "explorer" && <ExplorerTab hours={hours} />}
				{activeTab === "insights" && <InsightsTab hours={hours} />}
			</div>
		</div>
	);
}
