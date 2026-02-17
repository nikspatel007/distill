import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import type { ContentCalendar, ContentIdea } from "../../shared/schemas.js";
import { TagBadge } from "../components/shared/TagBadge.js";

function platformColor(platform: string): string {
	switch (platform.toLowerCase()) {
		case "blog":
			return "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200";
		case "social":
			return "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200";
		case "both":
			return "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200";
		default:
			return "bg-zinc-100 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-200";
	}
}

function statusColor(status: string): string {
	switch (status.toLowerCase()) {
		case "published":
			return "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200";
		case "in_progress":
			return "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200";
		default:
			return "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400";
	}
}

function IdeaCard({ idea }: { idea: ContentIdea }) {
	return (
		<div className="rounded-lg border border-zinc-200 p-4 transition-colors hover:border-zinc-400 dark:border-zinc-800 dark:hover:border-zinc-600">
			<div className="flex items-start justify-between gap-3">
				<h3 className="font-semibold text-zinc-900 dark:text-zinc-100">{idea.title}</h3>
				<div className="flex shrink-0 gap-1.5">
					<span
						className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${platformColor(idea.platform)}`}
					>
						{idea.platform}
					</span>
					<span
						className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${statusColor(idea.status)}`}
					>
						{idea.status}
					</span>
				</div>
			</div>
			<p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">{idea.angle}</p>
			<p className="mt-2 text-xs text-zinc-500">{idea.rationale}</p>
			{idea.pillars.length > 0 && (
				<div className="mt-2 flex flex-wrap gap-1">
					{idea.pillars.map((p) => (
						<TagBadge key={p} tag={p} />
					))}
				</div>
			)}
			{idea.tags.length > 0 && (
				<div className="mt-1.5 flex flex-wrap gap-1">
					{idea.tags.map((t) => (
						<span
							key={t}
							className="inline-block rounded bg-zinc-100 px-1.5 py-0.5 text-xs text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400"
						>
							{t}
						</span>
					))}
				</div>
			)}
			{idea.source_url && (
				<a
					href={idea.source_url}
					target="_blank"
					rel="noopener noreferrer"
					className="mt-2 inline-block text-xs text-indigo-600 hover:underline dark:text-indigo-400"
				>
					Source
				</a>
			)}
		</div>
	);
}

export default function Calendar() {
	const [selectedDate, setSelectedDate] = useState<string | null>(null);

	const { data: listData, isLoading: listLoading } = useQuery<{ calendars: string[] }>({
		queryKey: ["calendar-list"],
		queryFn: async () => {
			const res = await fetch("/api/calendar");
			if (!res.ok) throw new Error("Failed to load calendar list");
			return res.json();
		},
	});

	const dates = listData?.calendars ?? [];
	const activeDate = selectedDate ?? dates[0] ?? null;

	const { data: calendarData, isLoading: calendarLoading } = useQuery<ContentCalendar>({
		queryKey: ["calendar-detail", activeDate],
		queryFn: async () => {
			const res = await fetch(`/api/calendar/${activeDate}`);
			if (!res.ok) throw new Error("Failed to load calendar");
			return res.json();
		},
		enabled: !!activeDate,
	});

	const ideas = calendarData?.ideas ?? [];

	return (
		<div className="space-y-6">
			<h2 className="text-2xl font-bold">Content Calendar</h2>

			{listLoading ? (
				<div className="animate-pulse text-zinc-400">Loading calendars...</div>
			) : dates.length === 0 ? (
				<p className="text-sm text-zinc-500">
					No content calendars yet. Run <code>distill brainstorm</code> to generate ideas.
				</p>
			) : (
				<>
					{/* Date selector */}
					<div className="flex flex-wrap gap-2">
						{dates.map((d) => (
							<button
								key={d}
								type="button"
								onClick={() => setSelectedDate(d)}
								className={`rounded-lg border px-3 py-1.5 text-sm transition-colors ${
									d === activeDate
										? "border-indigo-600 bg-indigo-50 text-indigo-700 dark:border-indigo-400 dark:bg-indigo-950 dark:text-indigo-300"
										: "border-zinc-200 bg-white text-zinc-700 hover:border-zinc-400 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300 dark:hover:border-zinc-500"
								}`}
							>
								{d}
							</button>
						))}
					</div>

					{/* Calendar content */}
					{calendarLoading ? (
						<div className="animate-pulse text-zinc-400">Loading ideas...</div>
					) : ideas.length === 0 ? (
						<p className="text-sm text-zinc-500">No ideas for this date.</p>
					) : (
						<div className="space-y-3">
							<p className="text-sm text-zinc-500">
								{ideas.length} idea{ideas.length !== 1 ? "s" : ""} for {activeDate}
							</p>
							{ideas.map((idea, i) => (
								<IdeaCard key={`${idea.title}-${i}`} idea={idea} />
							))}
						</div>
					)}
				</>
			)}
		</div>
	);
}
