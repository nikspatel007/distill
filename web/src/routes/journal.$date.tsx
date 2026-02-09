import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "@tanstack/react-router";
import { useState } from "react";
import type { JournalDetail } from "../../shared/schemas.js";
import { DateBadge } from "../components/shared/DateBadge.js";
import { EditToggle } from "../components/shared/EditToggle.js";
import { MarkdownEditor } from "../components/shared/MarkdownEditor.js";
import { MarkdownRenderer } from "../components/shared/MarkdownRenderer.js";
import { useMarkdownSave } from "../lib/useMarkdownSave.js";

export default function JournalDetailPage() {
	const { date } = useParams({ from: "/journal/$date" });
	const [isEditing, setIsEditing] = useState(false);
	const { data, isLoading, error } = useQuery<JournalDetail>({
		queryKey: ["journal", date],
		queryFn: async () => {
			const res = await fetch(`/api/journal/${date}`);
			if (!res.ok) throw new Error("Journal entry not found");
			return res.json();
		},
	});

	const { editedContent, setEditedContent, isDirty, save, isSaving, saveSuccess } = useMarkdownSave(
		{
			endpoint: `/api/journal/${date}`,
			queryKey: ["journal", date],
			originalContent: data?.content ?? "",
		},
	);

	if (isLoading) return <div className="animate-pulse text-zinc-400">Loading...</div>;
	if (error) return <div className="text-red-500">Error: {error.message}</div>;
	if (!data) return null;

	return (
		<div className="space-y-4">
			<div className="flex items-center justify-between">
				<Link
					to="/journal"
					className="text-sm text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"
				>
					&larr; Journal
				</Link>
				<EditToggle
					isEditing={isEditing}
					onToggle={() => setIsEditing(!isEditing)}
					onSave={save}
					isSaving={isSaving}
					isDirty={isDirty}
					saveSuccess={saveSuccess}
				/>
			</div>

			<div className="flex items-center gap-3">
				<DateBadge date={data.meta.date} />
				<span className="text-sm text-zinc-500">{data.meta.style}</span>
				<span className="text-sm text-zinc-500">{data.meta.sessionsCount} sessions</span>
				<span className="text-sm text-zinc-500">{data.meta.durationMinutes}m</span>
			</div>

			{isEditing ? (
				<MarkdownEditor value={editedContent} onChange={setEditedContent} onSave={save} />
			) : (
				<MarkdownRenderer content={data.content} />
			)}
		</div>
	);
}
