import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import type { JournalEntry } from "../../shared/schemas.js";
import { DateBadge } from "../components/shared/DateBadge.js";
import { TagBadge } from "../components/shared/TagBadge.js";

export default function JournalList() {
	const { data, isLoading } = useQuery<{ entries: JournalEntry[] }>({
		queryKey: ["journal"],
		queryFn: async () => {
			const res = await fetch("/api/journal");
			if (!res.ok) throw new Error("Failed to load journal");
			return res.json();
		},
	});

	if (isLoading) return <div className="animate-pulse text-zinc-400">Loading journal...</div>;

	const entries = data?.entries ?? [];

	return (
		<div className="space-y-6">
			<h2 className="text-2xl font-bold">Journal</h2>
			{entries.length === 0 ? (
				<p className="text-zinc-500">
					No journal entries yet. Run <code>distill journal</code> to generate some.
				</p>
			) : (
				<div className="space-y-2">
					{entries.map((entry) => (
						<Link
							key={entry.filename}
							to="/journal/$date"
							params={{ date: entry.date }}
							className="block rounded-lg border border-zinc-200 p-4 transition-colors hover:bg-zinc-50 dark:border-zinc-800 dark:hover:bg-zinc-900"
						>
							<div className="flex items-center justify-between">
								<div className="flex items-center gap-2">
									<DateBadge date={entry.date} />
									<span className="text-sm text-zinc-500">{entry.style}</span>
								</div>
								<span className="text-xs text-zinc-500">
									{entry.sessionsCount} sessions, {entry.durationMinutes}m
								</span>
							</div>
							<div className="mt-2 flex flex-wrap gap-1">
								{entry.projects.map((p) => (
									<TagBadge key={p} tag={p} />
								))}
								{entry.tags
									.filter((t) => t !== "journal")
									.slice(0, 5)
									.map((t) => (
										<span
											key={t}
											className="rounded bg-zinc-100 px-1.5 py-0.5 text-xs dark:bg-zinc-800"
										>
											{t}
										</span>
									))}
							</div>
						</Link>
					))}
				</div>
			)}
		</div>
	);
}
