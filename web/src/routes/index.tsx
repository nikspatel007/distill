import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import {
	Bookmark,
	ChevronDown,
	ChevronLeft,
	ChevronRight,
	ChevronUp,
	ExternalLink,
	Lightbulb,
	PenLine,
	Sparkles,
	X,
} from "lucide-react";
import { useState } from "react";
import type { DailyBriefing, ReadingItemBrief } from "../../shared/schemas.js";

function formatDisplayDate(dateStr: string): string {
	if (dateStr === "today") return new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric", year: "numeric" });
	const d = new Date(dateStr + "T12:00:00");
	return d.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric", year: "numeric" });
}

function shiftDate(dateStr: string, days: number): string {
	const base = dateStr === "today" ? new Date() : new Date(dateStr + "T12:00:00");
	base.setDate(base.getDate() + days);
	return base.toISOString().slice(0, 10);
}

function isToday(dateStr: string): boolean {
	if (dateStr === "today") return true;
	const today = new Date().toISOString().slice(0, 10);
	return dateStr === today;
}

const statusBadgeClass: Record<string, string> = {
	draft: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200",
	approved: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
	published: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
};

export default function DailyBriefing() {
	const [date, setDate] = useState("today");
	const [readingOpen, setReadingOpen] = useState(true);
	const queryClient = useQueryClient();
	const navigate = useNavigate();

	const { data, isLoading, error } = useQuery<DailyBriefing>({
		queryKey: ["home", date],
		queryFn: async () => {
			const res = await fetch(`/api/home/${date}`);
			if (!res.ok) throw new Error("Failed to load briefing");
			return res.json();
		},
	});

	const dismissSeed = useMutation({
		mutationFn: async (seedId: string) => {
			const res = await fetch(`/api/seeds/${seedId}`, { method: "DELETE" });
			if (!res.ok) throw new Error("Failed to dismiss seed");
		},
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["home", date] });
		},
	});

	const saveSeed = useMutation({
		mutationFn: async (item: ReadingItemBrief) => {
			const res = await fetch("/api/seeds", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ text: `${item.title} - ${item.url}` }),
			});
			if (!res.ok) throw new Error("Failed to save seed");
		},
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["home", date] });
		},
	});

	const writeAbout = useMutation({
		mutationFn: async (item: ReadingItemBrief) => {
			const res = await fetch("/api/studio/items", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					title: item.title,
					body: `Source: ${item.url}\n\n${item.excerpt}`,
					content_type: "journal",
					tags: [],
				}),
			});
			if (!res.ok) throw new Error("Failed to create studio item");
			return res.json() as Promise<{ slug: string }>;
		},
		onSuccess: (result) => {
			navigate({ to: "/studio/$slug", params: { slug: result.slug } });
		},
	});

	const approveItem = useMutation({
		mutationFn: async (slug: string) => {
			const res = await fetch(`/api/studio/items/${slug}/status`, {
				method: "PUT",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ status: "ready" }),
			});
			if (!res.ok) throw new Error("Failed to approve");
		},
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["home", date] });
		},
	});

	const brainstorm = useMutation({
		mutationFn: async () => {
			// 1. Assemble today's context
			const ctxRes = await fetch("/api/home/brainstorm", { method: "POST" });
			if (!ctxRes.ok) throw new Error("Failed to assemble context");
			const ctx = (await ctxRes.json()) as { title: string; body: string; date: string };
			// 2. Create a Studio draft with it
			const studioRes = await fetch("/api/studio/items", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					title: ctx.title,
					body: ctx.body,
					content_type: "daily_social",
					source_date: ctx.date,
					tags: ["brainstorm"],
				}),
			});
			if (!studioRes.ok) throw new Error("Failed to create draft");
			return studioRes.json() as Promise<{ slug: string }>;
		},
		onSuccess: (result) => {
			navigate({ to: "/studio/$slug", params: { slug: result.slug } });
		},
	});

	if (isLoading)
		return (
			<div className="mx-auto max-w-2xl p-4 md:p-6">
				<div className="animate-pulse text-zinc-400">Loading briefing...</div>
			</div>
		);
	if (error)
		return (
			<div className="mx-auto max-w-2xl p-4 md:p-6">
				<div className="text-red-500">Error: {error.message}</div>
			</div>
		);
	if (!data) return null;

	const journal = data.journal;
	const intake = data.intake;
	const publishQueue = data.publishQueue ?? [];
	const seeds = (data.seeds ?? []).filter((s) => !s.used);
	const readingItems = data.readingItems ?? [];

	return (
		<div className="mx-auto max-w-2xl p-6 space-y-6">
			{/* Date navigation */}
			<div className="flex items-center justify-between">
				<button
					type="button"
					onClick={() => setDate(shiftDate(date, -1))}
					className="rounded-lg p-2 text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-800"
					aria-label="Previous day"
				>
					<ChevronLeft className="h-5 w-5" />
				</button>
				<div className="flex items-center gap-3">
					<h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
						{formatDisplayDate(date)}
					</h1>
					{!isToday(date) && (
						<button
							type="button"
							onClick={() => setDate("today")}
							className="rounded-full bg-indigo-600 px-3 py-1 text-xs font-medium text-white hover:bg-indigo-700"
						>
							Today
						</button>
					)}
				</div>
				<button
					type="button"
					onClick={() => setDate(shiftDate(date, 1))}
					className="rounded-lg p-2 text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-800"
					aria-label="Next day"
				>
					<ChevronRight className="h-5 w-5" />
				</button>
			</div>

			{/* Brainstorm CTA */}
			<button
				type="button"
				onClick={() => brainstorm.mutate()}
				disabled={brainstorm.isPending}
				className="flex w-full items-center justify-center gap-2 rounded-xl border-2 border-dashed border-indigo-300 bg-indigo-50/50 p-4 text-sm font-medium text-indigo-700 transition-colors hover:border-indigo-400 hover:bg-indigo-50 disabled:opacity-50 dark:border-indigo-700 dark:bg-indigo-950/30 dark:text-indigo-300 dark:hover:border-indigo-600 dark:hover:bg-indigo-950/50"
			>
				<Lightbulb className="h-5 w-5" />
				{brainstorm.isPending ? "Setting up..." : "What should I write about today?"}
			</button>

			{/* Today's reading card */}
			<section className="rounded-xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900">
				<button
					type="button"
					onClick={() => setReadingOpen(!readingOpen)}
					className="flex w-full items-center justify-between"
				>
					<h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
						Today&apos;s reading
					</h2>
					{readingOpen ? (
						<ChevronUp className="h-4 w-4 text-zinc-400" />
					) : (
						<ChevronDown className="h-4 w-4 text-zinc-400" />
					)}
				</button>
				{readingOpen && (
					<>
						{readingItems.length > 0 ? (
							<ul className="mt-3 space-y-3">
								{readingItems.map((item) => (
									<li
										key={item.id}
										className="rounded-lg border border-zinc-100 p-3 dark:border-zinc-800"
									>
										<div className="flex items-start justify-between gap-2">
											<div className="min-w-0 flex-1">
												<a
													href={item.url}
													target="_blank"
													rel="noopener noreferrer"
													className="text-sm font-medium text-zinc-900 hover:text-indigo-600 dark:text-zinc-100 dark:hover:text-indigo-400"
												>
													{item.title}
													<ExternalLink className="ml-1 inline h-3 w-3" />
												</a>
												<div className="mt-1 flex items-center gap-2">
													<span className="rounded bg-zinc-100 px-1.5 py-0.5 text-xs text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400">
														{item.site_name || item.source}
													</span>
													{item.word_count > 0 && (
														<span className="text-xs text-zinc-400">
															{item.word_count} words
														</span>
													)}
												</div>
												{item.excerpt && item.excerpt !== item.title && (
													<p className="mt-1.5 line-clamp-2 text-xs text-zinc-500">
														{item.excerpt}
													</p>
												)}
											</div>
											<div className="flex items-center gap-1.5 shrink-0">
												<button
													type="button"
													onClick={() => saveSeed.mutate(item)}
													className="rounded p-1.5 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600 dark:hover:bg-zinc-800"
													title="Save as seed idea"
												>
													<Bookmark className="h-3.5 w-3.5" />
												</button>
												<button
													type="button"
													onClick={() => writeAbout.mutate(item)}
													className="rounded p-1.5 text-zinc-400 hover:bg-zinc-100 hover:text-indigo-600 dark:hover:bg-zinc-800"
													title="Write about this"
												>
													<PenLine className="h-3.5 w-3.5" />
												</button>
											</div>
										</div>
									</li>
								))}
							</ul>
						) : (
							<p className="mt-2 text-sm text-zinc-400">
								Run <code className="rounded bg-zinc-100 px-1.5 py-0.5 text-xs dark:bg-zinc-800">distill intake</code> to load your feeds
							</p>
						)}
					</>
				)}
			</section>

			{/* Journal card */}
			<section className="rounded-xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900">
				<h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
					What you built
				</h2>
				{journal.brief.length > 0 ? (
					<>
						<p className="mt-1 text-sm text-zinc-500">
							{journal.sessionsCount} sessions &middot; {journal.durationMinutes}m
						</p>
						<ul className="mt-3 space-y-1">
							{journal.brief.map((item) => (
								<li key={item} className="text-sm text-zinc-700 dark:text-zinc-300">
									&bull; {item}
								</li>
							))}
						</ul>
						{journal.hasFullEntry && (
							<Link
								to="/journal/$date"
								params={{ date: journal.date }}
								className="mt-3 inline-block text-sm font-medium text-indigo-600 hover:text-indigo-700"
							>
								Read more
							</Link>
						)}
					</>
				) : (
					<p className="mt-2 text-sm text-zinc-400">No journal entry for this date</p>
				)}
			</section>

			{/* Intake card */}
			<section className="rounded-xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900">
				<h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
					What you read
				</h2>
				{intake.highlights.length > 0 ? (
					<>
						<p className="mt-1 text-sm text-zinc-500">{intake.itemCount} items</p>
						<ul className="mt-3 space-y-1">
							{intake.highlights.map((item) => (
								<li key={item} className="text-sm text-zinc-700 dark:text-zinc-300">
									&bull; {item}
								</li>
							))}
						</ul>
						{intake.hasFullDigest && (
							<Link
								to="/reading/$date"
								params={{ date: intake.date }}
								className="mt-3 inline-block text-sm font-medium text-indigo-600 hover:text-indigo-700"
							>
								Read more
							</Link>
						)}
					</>
				) : (
					<p className="mt-2 text-sm text-zinc-400">No intake digest for this date</p>
				)}
			</section>

			{/* Publish queue card */}
			<section className="rounded-xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900">
				<h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
					Ready to publish
				</h2>
				{publishQueue.length > 0 ? (
					<ul className="mt-3 space-y-3">
						{publishQueue.map((item) => (
							<li
								key={item.slug}
								className="flex items-center justify-between gap-2"
							>
								<div className="min-w-0 flex-1">
									<span className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
										{item.title}
									</span>
									<div className="mt-0.5 flex items-center gap-2">
										<span className="rounded bg-zinc-100 px-1.5 py-0.5 text-xs dark:bg-zinc-800">
											{item.type}
										</span>
										<span
											className={`rounded px-1.5 py-0.5 text-xs ${statusBadgeClass[item.status] ?? ""}`}
										>
											{item.platforms_published}/{item.platforms_total} published
										</span>
									</div>
								</div>
								<div className="flex items-center gap-2 shrink-0">
									{item.status !== "published" && (
										<button
											type="button"
											onClick={() => approveItem.mutate(item.slug)}
											disabled={approveItem.isPending}
											className={
												approveItem.variables === item.slug &&
												approveItem.isSuccess
													? "rounded bg-green-600 px-3 py-1 text-xs font-medium text-white"
													: "rounded bg-indigo-600 px-3 py-1 text-xs font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
											}
										>
											{approveItem.variables === item.slug &&
											approveItem.isSuccess
												? "Approved"
												: "Approve"}
										</button>
									)}
									<Link
										to="/studio/$slug"
										params={{ slug: item.slug }}
										className="text-xs font-medium text-indigo-600 hover:text-indigo-700"
									>
										Edit in Studio
									</Link>
								</div>
							</li>
						))}
					</ul>
				) : (
					<p className="mt-2 text-sm text-zinc-400">Nothing to publish</p>
				)}
			</section>

			{/* Seeds card */}
			{seeds.length > 0 && (
				<section className="rounded-xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900">
					<h2 className="flex items-center gap-2 text-base font-semibold text-zinc-900 dark:text-zinc-100">
						<Sparkles className="h-4 w-4" />
						Ideas
					</h2>
					<ul className="mt-3 space-y-3">
						{seeds.map((seed) => (
							<li key={seed.id} className="flex items-start justify-between gap-2">
								<span className="text-sm text-zinc-700 dark:text-zinc-300">
									{seed.text}
								</span>
								<div className="flex items-center gap-2 shrink-0">
									<Link
										to="/studio"
										className="text-xs font-medium text-indigo-600 hover:text-indigo-700"
									>
										Develop
									</Link>
									<button
										type="button"
										onClick={() => dismissSeed.mutate(seed.id)}
										className="rounded p-1 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600 dark:hover:bg-zinc-800"
										aria-label="Dismiss seed"
									>
										<X className="h-3.5 w-3.5" />
									</button>
								</div>
							</li>
						))}
					</ul>
				</section>
			)}
		</div>
	);
}
