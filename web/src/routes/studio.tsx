import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { PenLine, X } from "lucide-react";
import { useState } from "react";
import type { JournalEntry } from "../../shared/schemas.js";
import { DateBadge } from "../components/shared/DateBadge.js";
import { DEFAULT_TYPE_STYLE, StatusBadge, TYPE_STYLES } from "../components/studio/styles.js";

interface StudioItem {
	slug: string;
	title: string;
	type: string;
	status: string;
	generated_at: string;
	platforms_ready: number;
	platforms_published: number;
}

export default function Studio() {
	const [showJournalPicker, setShowJournalPicker] = useState(false);
	const queryClient = useQueryClient();
	const navigate = useNavigate();

	const { data, isLoading } = useQuery<{ items: StudioItem[] }>({
		queryKey: ["studio-items"],
		queryFn: async () => {
			const res = await fetch("/api/studio/items");
			if (!res.ok) throw new Error("Failed to load studio items");
			return res.json();
		},
	});

	const items = data?.items ?? [];

	if (isLoading) {
		return <div className="animate-pulse text-zinc-400">Loading content...</div>;
	}

	return (
		<div className="space-y-6">
			<div className="flex items-center justify-between">
				<div>
					<h2 className="text-2xl font-bold">Content Studio</h2>
					<p className="mt-1 text-sm text-zinc-500">
						Craft posts from your journals, refine with Claude, and publish.
					</p>
				</div>
				<button
					type="button"
					onClick={() => setShowJournalPicker(true)}
					className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
				>
					<PenLine className="h-4 w-4" />
					New Post
				</button>
			</div>

			{items.length === 0 ? (
				<div className="rounded-lg border border-zinc-200 p-8 text-center dark:border-zinc-800">
					<p className="text-zinc-500">
						No content yet. Click <strong>New Post</strong> to start writing from a journal entry.
					</p>
				</div>
			) : (
				<div className="space-y-2">
					{items.map((item) => (
						<Link
							key={item.slug}
							to="/studio/$slug"
							params={{ slug: item.slug }}
							className="flex items-center justify-between rounded-lg border border-zinc-200 p-4 transition-colors hover:border-indigo-300 hover:bg-indigo-50/50 dark:border-zinc-800 dark:hover:border-indigo-800 dark:hover:bg-indigo-950/30"
						>
							<div className="flex items-center gap-3">
								<div>
									<div className="flex items-center gap-2">
										<span className="font-medium">{item.title}</span>
										<span
											className={`rounded-full px-2 py-0.5 text-xs font-medium ${TYPE_STYLES[item.type] ?? DEFAULT_TYPE_STYLE}`}
										>
											{item.type.replace("_", " ")}
										</span>
									</div>
									<div className="mt-1 flex items-center gap-3 text-xs text-zinc-500">
										<DateBadge date={item.generated_at} />
										{item.platforms_ready > 0 && (
											<span>
												{item.platforms_ready} platform
												{item.platforms_ready !== 1 ? "s" : ""} ready
											</span>
										)}
										{item.platforms_published > 0 && (
											<span className="text-green-600">{item.platforms_published} published</span>
										)}
									</div>
								</div>
							</div>
							<StatusBadge status={item.status} />
						</Link>
					))}
				</div>
			)}

			{showJournalPicker && (
				<JournalPickerModal
					onClose={() => setShowJournalPicker(false)}
					onCreated={(slug) => {
						setShowJournalPicker(false);
						queryClient.invalidateQueries({ queryKey: ["studio-items"] });
						navigate({ to: "/studio/$slug", params: { slug } });
					}}
				/>
			)}
		</div>
	);
}

// ---------------------------------------------------------------------------
// Journal Picker Modal
// ---------------------------------------------------------------------------

function JournalPickerModal({
	onClose,
	onCreated,
}: {
	onClose: () => void;
	onCreated: (slug: string) => void;
}) {
	const [customTitle, setCustomTitle] = useState("");

	const { data: journalData, isLoading } = useQuery<{ entries: JournalEntry[] }>({
		queryKey: ["journal-entries"],
		queryFn: async () => {
			const res = await fetch("/api/journal");
			if (!res.ok) throw new Error("Failed to load journals");
			return res.json();
		},
	});

	const createMutation = useMutation({
		mutationFn: async (entry: JournalEntry) => {
			// Fetch the full journal content
			const detailRes = await fetch(`/api/journal/${entry.date}`);
			if (!detailRes.ok) throw new Error("Failed to load journal");
			const detail = (await detailRes.json()) as { content: string };

			const title = customTitle.trim() || `Post from ${entry.date}`;

			const res = await fetch("/api/studio/items", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					title,
					body: detail.content,
					content_type: "journal",
					source_date: entry.date,
					tags: entry.projects,
				}),
			});
			if (!res.ok) {
				const err = await res.json().catch(() => ({ error: "Create failed" }));
				throw new Error(err.error || "Failed to create");
			}
			return res.json() as Promise<{ slug: string }>;
		},
		onSuccess: (data) => {
			onCreated(data.slug);
		},
	});

	const entries = journalData?.entries ?? [];
	// Sort most recent first
	const sorted = [...entries].sort((a, b) => b.date.localeCompare(a.date));

	return (
		<div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
			<div className="mx-4 w-full max-w-lg rounded-xl border border-zinc-200 bg-white shadow-2xl dark:border-zinc-700 dark:bg-zinc-900">
				{/* Header */}
				<div className="flex items-center justify-between border-b border-zinc-200 px-5 py-3 dark:border-zinc-700">
					<h3 className="text-lg font-semibold">New Post from Journal</h3>
					<button
						type="button"
						onClick={onClose}
						className="rounded-lg p-1 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600 dark:hover:bg-zinc-800"
					>
						<X className="h-5 w-5" />
					</button>
				</div>

				{/* Title input */}
				<div className="border-b border-zinc-100 px-5 py-3 dark:border-zinc-800">
					<label htmlFor="post-title" className="block text-xs font-medium text-zinc-500 mb-1.5">
						Post title (optional — you can change it later)
					</label>
					<input
						id="post-title"
						type="text"
						value={customTitle}
						onChange={(e) => setCustomTitle(e.target.value)}
						placeholder="e.g. What I learned about agent orchestration"
						className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm placeholder-zinc-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 dark:border-zinc-600 dark:bg-zinc-800 dark:placeholder-zinc-500"
					/>
				</div>

				{/* Journal list */}
				<div className="max-h-80 overflow-y-auto px-5 py-3">
					{isLoading ? (
						<div className="py-8 text-center text-sm text-zinc-400 animate-pulse">
							Loading journals...
						</div>
					) : sorted.length === 0 ? (
						<div className="py-8 text-center text-sm text-zinc-400">
							No journal entries found. Run{" "}
							<code className="rounded bg-zinc-100 px-1 text-xs dark:bg-zinc-800">
								distill journal
							</code>{" "}
							first.
						</div>
					) : (
						<div className="space-y-1">
							{sorted.slice(0, 14).map((entry) => (
								<button
									key={entry.date}
									type="button"
									disabled={createMutation.isPending}
									onClick={() => createMutation.mutate(entry)}
									className="flex w-full items-center justify-between rounded-lg px-3 py-2.5 text-left transition-colors hover:bg-indigo-50 disabled:opacity-50 dark:hover:bg-indigo-950/30"
								>
									<div>
										<span className="text-sm font-medium">{entry.date}</span>
										{entry.projects.length > 0 && (
											<span className="ml-2 text-xs text-zinc-400">
												{entry.projects.join(", ")}
											</span>
										)}
									</div>
									<div className="flex items-center gap-2 text-xs text-zinc-400">
										{entry.sessionsCount > 0 && (
											<span>
												{entry.sessionsCount} session{entry.sessionsCount !== 1 ? "s" : ""}
											</span>
										)}
										{entry.durationMinutes > 0 && (
											<span>{Math.round(entry.durationMinutes / 60)}h</span>
										)}
									</div>
								</button>
							))}
						</div>
					)}
				</div>

				{createMutation.isPending && (
					<div className="border-t border-zinc-100 px-5 py-3 text-center text-sm text-indigo-600 animate-pulse dark:border-zinc-800">
						Creating post...
					</div>
				)}
				{createMutation.error && (
					<div className="border-t border-zinc-100 px-5 py-3 text-center text-sm text-red-500 dark:border-zinc-800">
						{createMutation.error.message}
					</div>
				)}
			</div>
		</div>
	);
}
