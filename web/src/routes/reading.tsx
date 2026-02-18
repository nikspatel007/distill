import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useState } from "react";
import type { ContentItemsResponse, IntakeDigest, SeedIdea } from "../../shared/schemas.js";
import { ContentItemCard } from "../components/shared/ContentItemCard.js";
import { DateBadge } from "../components/shared/DateBadge.js";
import { SourceFilterPills } from "../components/shared/SourceFilterPills.js";

type Tab = "items" | "digests";

export default function Reading() {
	const queryClient = useQueryClient();
	const [newSeed, setNewSeed] = useState("");
	const [activeTab, setActiveTab] = useState<Tab>("items");
	const [filterSource, setFilterSource] = useState<string | null>(null);
	const [selectedDate, setSelectedDate] = useState<string | null>(null);
	const [page, setPage] = useState(1);
	const [seedsOpen, setSeedsOpen] = useState(false);

	const { data: digestsData, isLoading: digestsLoading } = useQuery<{ digests: IntakeDigest[] }>({
		queryKey: ["reading"],
		queryFn: async () => {
			const res = await fetch("/api/reading/digests");
			if (!res.ok) throw new Error("Failed to load digests");
			return res.json();
		},
	});

	// Fetch available archive dates (independent of digests)
	const { data: archiveDatesData } = useQuery<{ dates: string[] }>({
		queryKey: ["reading-archive-dates"],
		queryFn: async () => {
			const res = await fetch("/api/reading/items");
			if (!res.ok) throw new Error("Failed to load archive dates");
			return res.json();
		},
	});

	const { data: seedsData } = useQuery<{ seeds: SeedIdea[] }>({
		queryKey: ["seeds"],
		queryFn: async () => {
			const res = await fetch("/api/seeds");
			if (!res.ok) throw new Error("Failed to load seeds");
			return res.json();
		},
	});

	const digests = digestsData?.digests ?? [];
	const archiveDates = archiveDatesData?.dates ?? [];
	const activeDate = selectedDate ?? archiveDates[0] ?? null;

	const { data: itemsData, isLoading: itemsLoading } = useQuery<ContentItemsResponse>({
		queryKey: ["reading-items", activeDate, filterSource, page],
		queryFn: async () => {
			const params = new URLSearchParams();
			if (activeDate) params.set("date", activeDate);
			if (filterSource) params.set("source", filterSource);
			params.set("page", String(page));
			const res = await fetch(`/api/reading/items?${params.toString()}`);
			if (!res.ok) throw new Error("Failed to load items");
			return res.json();
		},
		enabled: activeTab === "items" && !!activeDate,
	});

	const addSeed = useMutation({
		mutationFn: async (text: string) => {
			const res = await fetch("/api/seeds", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ text, tags: [] }),
			});
			if (!res.ok) throw new Error("Failed to add seed");
			return res.json();
		},
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["seeds"] });
			setNewSeed("");
		},
	});

	const deleteSeed = useMutation({
		mutationFn: async (id: string) => {
			const res = await fetch(`/api/seeds/${id}`, { method: "DELETE" });
			if (!res.ok) throw new Error("Failed to delete seed");
		},
		onSuccess: () => queryClient.invalidateQueries({ queryKey: ["seeds"] }),
	});

	const seeds = seedsData?.seeds ?? [];
	const items = itemsData?.items ?? [];
	const availableSources = itemsData?.available_sources ?? [];
	const totalItems = itemsData?.total_items ?? 0;
	const totalPages = itemsData?.total_pages ?? 1;
	const currentPage = itemsData?.page ?? 1;

	const rangeStart = totalItems === 0 ? 0 : (currentPage - 1) * 50 + 1;
	const rangeEnd = rangeStart === 0 ? 0 : rangeStart + items.length - 1;

	return (
		<div className="space-y-6">
			<h2 className="text-2xl font-bold">Reading</h2>

			{/* Tab bar */}
			<div className="border-b border-zinc-200 dark:border-zinc-800">
				<nav className="-mb-px flex gap-4" aria-label="Content tabs">
					<button
						type="button"
						onClick={() => setActiveTab("items")}
						className={`border-b-2 px-1 pb-2 text-sm font-medium transition-colors ${
							activeTab === "items"
								? "border-indigo-600 text-indigo-600 dark:border-indigo-400 dark:text-indigo-400"
								: "border-transparent text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300"
						}`}
					>
						Items
					</button>
					<button
						type="button"
						onClick={() => setActiveTab("digests")}
						className={`border-b-2 px-1 pb-2 text-sm font-medium transition-colors ${
							activeTab === "digests"
								? "border-indigo-600 text-indigo-600 dark:border-indigo-400 dark:text-indigo-400"
								: "border-transparent text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300"
						}`}
					>
						Digests
					</button>
				</nav>
			</div>

			{/* Items tab */}
			{activeTab === "items" && (
				<section>
					<div className="flex flex-wrap items-center gap-3">
						{archiveDates.length > 1 && (
							<select
								value={activeDate ?? ""}
								onChange={(e) => {
									setSelectedDate(e.target.value || null);
									setFilterSource(null);
									setPage(1);
								}}
								className="rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
							>
								{archiveDates.map((d) => (
									<option key={d} value={d}>
										{d}
									</option>
								))}
							</select>
						)}
						<SourceFilterPills
							sources={availableSources}
							filterSource={filterSource}
							onFilterChange={(s) => {
								setFilterSource(s);
								setPage(1);
							}}
						/>
					</div>
					{itemsLoading ? (
						<div className="mt-4 animate-pulse text-zinc-400">Loading items...</div>
					) : items.length === 0 ? (
						<p className="mt-4 text-sm text-zinc-500">
							No content items yet. Run <code>distill intake</code> to ingest content.
						</p>
					) : (
						<>
							<div className="mt-4 space-y-3">
								{items.map((item) => (
									<ContentItemCard key={item.id} item={item} />
								))}
							</div>
							{/* Pagination controls */}
							<div className="mt-4 flex items-center justify-between text-sm">
								<span className="text-zinc-500">
									Showing {rangeStart}–{rangeEnd} of {totalItems} items
								</span>
								<div className="flex gap-2">
									<button
										type="button"
										disabled={currentPage <= 1}
										onClick={() => setPage((p) => Math.max(1, p - 1))}
										className="rounded border border-zinc-300 px-3 py-1 text-sm transition-colors hover:bg-zinc-100 disabled:opacity-40 dark:border-zinc-700 dark:hover:bg-zinc-800"
									>
										Prev
									</button>
									<span className="flex items-center px-2 text-zinc-500">
										{currentPage} / {totalPages}
									</span>
									<button
										type="button"
										disabled={currentPage >= totalPages}
										onClick={() => setPage((p) => p + 1)}
										className="rounded border border-zinc-300 px-3 py-1 text-sm transition-colors hover:bg-zinc-100 disabled:opacity-40 dark:border-zinc-700 dark:hover:bg-zinc-800"
									>
										Next
									</button>
								</div>
							</div>
						</>
					)}
				</section>
			)}

			{/* Digests tab */}
			{activeTab === "digests" && (
				<section>
					{digestsLoading ? (
						<div className="animate-pulse text-zinc-400">Loading digests...</div>
					) : digests.length === 0 ? (
						<p className="text-sm text-zinc-500">
							No intake digests yet. Run <code>distill intake</code> to generate some.
						</p>
					) : (
						<div className="space-y-2">
							{digests.map((d) => (
								<Link
									key={d.filename}
									to="/reading/$date"
									params={{ date: d.date }}
									className="block rounded-lg border border-zinc-200 p-4 transition-colors hover:border-zinc-400 dark:border-zinc-800 dark:hover:border-zinc-600"
								>
									<div className="flex items-center justify-between">
										<DateBadge date={d.date} />
										<span className="text-xs text-zinc-500">
											{d.itemCount} items from {d.sources.length} sources
										</span>
									</div>
								</Link>
							))}
						</div>
					)}
				</section>
			)}

			{/* Seeds section - collapsible, below tabs */}
			<section className="border-t border-zinc-200 pt-4 dark:border-zinc-800">
				<button
					type="button"
					onClick={() => setSeedsOpen(!seedsOpen)}
					className="flex w-full items-center gap-2 text-left"
				>
					<svg
						aria-hidden="true"
						className={`h-4 w-4 text-zinc-400 transition-transform ${seedsOpen ? "rotate-90" : ""}`}
						fill="none"
						viewBox="0 0 24 24"
						stroke="currentColor"
						strokeWidth={2}
					>
						<path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
					</svg>
					<h3 className="text-lg font-semibold">
						Seed Ideas{seeds.length > 0 ? ` (${seeds.length})` : ""}
					</h3>
				</button>
				{seedsOpen && (
					<div className="mt-3">
						<form
							className="mb-4 flex gap-2"
							onSubmit={(e) => {
								e.preventDefault();
								if (newSeed.trim()) addSeed.mutate(newSeed.trim());
							}}
						>
							<input
								type="text"
								value={newSeed}
								onChange={(e) => setNewSeed(e.target.value)}
								placeholder="Add a seed idea..."
								className="flex-1 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
							/>
							<button
								type="submit"
								disabled={!newSeed.trim() || addSeed.isPending}
								className="rounded-lg bg-indigo-600 px-4 py-2 text-sm text-white hover:bg-indigo-700 disabled:opacity-50"
							>
								Add
							</button>
						</form>
						{seeds.length === 0 ? (
							<p className="text-sm text-zinc-500">No seeds yet.</p>
						) : (
							<div className="space-y-2">
								{seeds.map((seed) => (
									<div
										key={seed.id}
										className="flex items-center justify-between rounded-lg border border-zinc-200 p-3 dark:border-zinc-800"
									>
										<div>
											<span className={seed.used ? "text-zinc-400 line-through" : ""}>
												{seed.text}
											</span>
											{seed.tags.length > 0 && (
												<span className="ml-2 text-xs text-zinc-500">{seed.tags.join(", ")}</span>
											)}
										</div>
										<button
											type="button"
											onClick={() => deleteSeed.mutate(seed.id)}
											className="text-xs text-red-500 hover:text-red-700"
										>
											Delete
										</button>
									</div>
								))}
							</div>
						)}
					</div>
				)}
			</section>
		</div>
	);
}
