import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import {
	Bookmark,
	ChevronDown,
	ChevronLeft,
	ChevronRight,
	ChevronUp,
	Check,
	Clipboard,
	Compass,
	ExternalLink,
	Lightbulb,
	Loader2,
	PenLine,
	RefreshCw,
	Send,
	Sparkles,
	X,
} from "lucide-react";
import { useState } from "react";
import type { DailyBriefing, DraftPost, ReadingItemBrief } from "../../shared/schemas.js";

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

function DraftCard({ draft, date }: { draft: DraftPost; date: string }) {
	const [editing, setEditing] = useState(false);
	const [content, setContent] = useState(draft.content);
	const queryClient = useQueryClient();

	const saveDraft = useMutation({
		mutationFn: async (newContent: string) => {
			const res = await fetch(`/api/home/drafts/${date}/${draft.platform}`, {
				method: "PATCH",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ content: newContent }),
			});
			if (!res.ok) throw new Error("Failed to save");
		},
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["home"] });
			setEditing(false);
		},
	});

	const publishDraft = useMutation({
		mutationFn: async () => {
			const res = await fetch(`/api/home/drafts/${date}/${draft.platform}/publish`, {
				method: "POST",
				headers: { "Content-Type": "application/json" },
			});
			if (!res.ok) {
				const data = await res.json().catch(() => ({}));
				throw new Error((data as { error?: string }).error ?? "Failed to publish");
			}
		},
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["home"] });
		},
	});

	const [copied, setCopied] = useState(false);

	const copyToClipboard = async () => {
		await navigator.clipboard.writeText(content);
		setCopied(true);
		setTimeout(() => setCopied(false), 2000);
	};

	const platformLabel = draft.platform === "linkedin" ? "LinkedIn" : "X";
	const charLimit = draft.platform === "linkedin" ? 3000 : 280;
	const charPct = Math.min((content.length / charLimit) * 100, 100);

	return (
		<div className="rounded-lg border border-zinc-100 p-3 dark:border-zinc-800">
			<div className="mb-2 flex items-center justify-between">
				<span className={`rounded-full px-2 py-0.5 text-xs font-medium ${
					draft.platform === "linkedin"
						? "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300"
						: "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300"
				}`}>
					{platformLabel}
				</span>
				<div className="flex items-center gap-2">
					<div className="flex items-center gap-1">
						<div className="h-1 w-16 rounded-full bg-zinc-200 dark:bg-zinc-700">
							<div
								className={`h-1 rounded-full ${charPct > 90 ? "bg-red-500" : "bg-indigo-400"}`}
								style={{ width: `${charPct}%` }}
							/>
						</div>
						<span className={`text-xs ${charPct > 90 ? "text-red-500" : "text-zinc-400"}`}>
							{content.length}/{charLimit}
						</span>
					</div>
				</div>
			</div>
			{editing ? (
				<div>
					<textarea
						value={content}
						onChange={(e) => setContent(e.target.value)}
						className="w-full rounded-lg border border-zinc-200 bg-zinc-50 p-3 text-sm dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-200"
						rows={8}
					/>
					<div className="mt-2 flex gap-2">
						<button
							type="button"
							onClick={() => saveDraft.mutate(content)}
							disabled={saveDraft.isPending}
							className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
						>
							{saveDraft.isPending ? "Saving..." : "Save"}
						</button>
						<button
							type="button"
							onClick={() => { setContent(draft.content); setEditing(false); }}
							className="rounded-lg px-3 py-1.5 text-xs text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-800"
						>
							Cancel
						</button>
					</div>
				</div>
			) : (
				<div>
					<p className="whitespace-pre-wrap text-sm text-zinc-700 dark:text-zinc-300">
						{draft.content}
					</p>
					<div className="mt-2 flex items-center gap-2">
						<button
							type="button"
							onClick={copyToClipboard}
							className="flex items-center gap-1 text-xs text-zinc-600 hover:text-zinc-800 dark:text-zinc-400 dark:hover:text-zinc-200"
						>
							{copied ? <Check className="h-3 w-3 text-green-500" /> : <Clipboard className="h-3 w-3" />}
							{copied ? "Copied!" : "Copy"}
						</button>
						<button
							type="button"
							onClick={() => setEditing(true)}
							className="flex items-center gap-1 text-xs text-indigo-600 hover:text-indigo-700"
						>
							<PenLine className="h-3 w-3" /> Edit
						</button>
						<button
							type="button"
							onClick={() => publishDraft.mutate()}
							disabled={publishDraft.isPending}
							className="flex items-center gap-1 text-xs text-green-600 hover:text-green-700 disabled:opacity-50"
						>
							<Send className="h-3 w-3" />
							{publishDraft.isPending ? "Sending..." : "Push to Postiz"}
						</button>
						{publishDraft.isError && (
							<span className="text-xs text-red-500">{publishDraft.error.message}</span>
						)}
						{publishDraft.isSuccess && (
							<span className="text-xs text-green-500">Sent!</span>
						)}
					</div>
				</div>
			)}
		</div>
	);
}

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

	const refreshPipeline = useMutation({
		mutationFn: async () => {
			const res = await fetch("/api/pipeline/run", { method: "POST" });
			if (!res.ok) throw new Error("Failed to start pipeline");
			// Poll until complete
			for (let i = 0; i < 60; i++) {
				await new Promise((r) => setTimeout(r, 3000));
				const status = await fetch("/api/pipeline/status");
				const data = await status.json() as { status: string };
				if (data.status === "completed") return;
				if (data.status === "failed") throw new Error("Pipeline failed");
			}
		},
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["home"] });
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
					<button
						type="button"
						onClick={() => refreshPipeline.mutate()}
						disabled={refreshPipeline.isPending}
						className="rounded-lg p-1.5 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600 disabled:opacity-50 dark:hover:bg-zinc-800"
						title="Refresh — run pipeline"
					>
						{refreshPipeline.isPending
							? <Loader2 className="h-4 w-4 animate-spin" />
							: <RefreshCw className="h-4 w-4" />
						}
					</button>
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

			{/* 3 Things Worth Knowing */}
			{data.readingBrief && data.readingBrief.highlights.length > 0 && (
				<section className="rounded-xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900">
					<h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
						3 things worth knowing
					</h2>
					<ul className="mt-3 space-y-4">
						{data.readingBrief.highlights.map((h) => (
							<li key={h.title} className="border-l-2 border-indigo-400 pl-3">
								<div className="flex items-start justify-between gap-2">
									<div>
										<span className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
											{h.title}
										</span>
										<span className="ml-2 text-xs text-zinc-400">
											{h.source}
										</span>
									</div>
									{h.url && (
										<a
											href={h.url}
											target="_blank"
											rel="noopener noreferrer"
											className="shrink-0 text-zinc-400 hover:text-indigo-500"
										>
											<ExternalLink className="h-3.5 w-3.5" />
										</a>
									)}
								</div>
								<p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
									{h.summary}
								</p>
							</li>
						))}
					</ul>
				</section>
			)}

			{/* Connection */}
			{data.readingBrief?.connection && (
				<section className="rounded-xl border border-amber-200 bg-amber-50/50 p-5 dark:border-amber-800 dark:bg-amber-950/30">
					<h2 className="text-base font-semibold text-amber-900 dark:text-amber-100">
						Connection
					</h2>
					<p className="mt-2 text-sm text-amber-800 dark:text-amber-200">
						{data.readingBrief.connection.explanation}
					</p>
					<div className="mt-2 flex items-center gap-2">
						<span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-700 dark:bg-amber-900 dark:text-amber-300">
							{data.readingBrief.connection.connection_type}
						</span>
					</div>
				</section>
			)}

			{/* Ready to Post */}
			{data.readingBrief && data.readingBrief.drafts.length > 0 && (
				<section className="rounded-xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900">
					<h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
						Ready to post
					</h2>
					<div className="mt-3 space-y-4">
						{data.readingBrief.drafts.map((draft) => (
							<DraftCard key={draft.platform} draft={draft} date={data.date} />
						))}
					</div>
				</section>
			)}

			{/* Learning Pulse */}
			{data.readingBrief && data.readingBrief.learning_pulse.length > 0 && (
				<section className="rounded-xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900">
					<h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
						Learning pulse
					</h2>
					<div className="mt-3 space-y-2">
						{data.readingBrief.learning_pulse.slice(0, 8).map((t) => (
							<div key={t.topic} className="flex items-center justify-between">
								<div className="flex items-center gap-2">
									<span className={`inline-block h-2 w-2 rounded-full ${
										t.status === "trending" ? "bg-green-500" :
										t.status === "emerging" ? "bg-blue-500" :
										t.status === "cooling" ? "bg-orange-500" :
										"bg-zinc-400"
									}`} />
									<span className="text-sm text-zinc-700 dark:text-zinc-300">{t.topic}</span>
								</div>
								<div className="flex items-center gap-2">
									<div className="flex items-end gap-px h-4">
										{t.sparkline.slice(-7).map((v, i) => (
											<div
												key={i}
												className={`w-1 rounded-t ${v > 0 ? "bg-indigo-400" : "bg-zinc-200 dark:bg-zinc-700"}`}
												style={{ height: `${Math.max(v * 25, 2)}px` }}
											/>
										))}
									</div>
									<span className={`rounded-full px-1.5 py-0.5 text-xs ${
										t.status === "trending" ? "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300" :
										t.status === "emerging" ? "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300" :
										t.status === "cooling" ? "bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300" :
										"bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400"
									}`}>
										{t.status}
									</span>
								</div>
							</div>
						))}
					</div>
				</section>
			)}

			{/* Explore Next */}
			{data.discovery && data.discovery.items.length > 0 && (
				<section className="rounded-xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900">
					<div className="flex items-center justify-between">
						<h2 className="flex items-center gap-2 text-base font-semibold text-zinc-900 dark:text-zinc-100">
							<Compass className="h-4 w-4 text-indigo-500" />
							Explore next
						</h2>
						{data.discovery.topics_searched.length > 0 && (
							<div className="flex gap-1">
								{data.discovery.topics_searched.slice(0, 3).map((t) => (
									<span key={t} className="rounded-full bg-zinc-100 px-2 py-0.5 text-xs text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400">
										{t}
									</span>
								))}
							</div>
						)}
					</div>
					<div className="mt-3 space-y-3">
						{data.discovery.items.map((item) => (
							<div key={item.url} className="rounded-lg border border-zinc-100 p-3 dark:border-zinc-800">
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
											{item.source && (
												<span className="rounded bg-zinc-100 px-1.5 py-0.5 text-xs text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400">
													{item.source}
												</span>
											)}
											{item.content_type !== "article" && (
												<span className="rounded bg-indigo-100 px-1.5 py-0.5 text-xs text-indigo-600 dark:bg-indigo-900 dark:text-indigo-300">
													{item.content_type}
												</span>
											)}
										</div>
										{item.summary && (
											<p className="mt-1.5 text-xs text-zinc-500 dark:text-zinc-400">
												{item.summary}
											</p>
										)}
									</div>
									<button
										type="button"
										onClick={() => saveSeed.mutate({ id: item.url, title: item.title, url: item.url, source: item.source, excerpt: item.summary, site_name: item.source, word_count: 0 })}
										className="shrink-0 rounded p-1.5 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600 dark:hover:bg-zinc-800"
										title="Save for later"
									>
										<Bookmark className="h-3.5 w-3.5" />
									</button>
								</div>
							</div>
						))}
					</div>
				</section>
			)}

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
