import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "@tanstack/react-router";
import { useState } from "react";
import type { IntakeDetail } from "../../shared/schemas.js";
import { DateBadge } from "../components/shared/DateBadge.js";
import { EditToggle } from "../components/shared/EditToggle.js";
import { MarkdownEditor } from "../components/shared/MarkdownEditor.js";
import { MarkdownRenderer } from "../components/shared/MarkdownRenderer.js";
import { useMarkdownSave } from "../lib/useMarkdownSave.js";

export default function ReadingDetailPage() {
	const { date } = useParams({ from: "/reading/$date" });
	const [isEditing, setIsEditing] = useState(false);
	const { data, isLoading, error } = useQuery<IntakeDetail>({
		queryKey: ["reading", date],
		queryFn: async () => {
			const res = await fetch(`/api/reading/digests/${date}`);
			if (!res.ok) throw new Error("Digest not found");
			return res.json();
		},
	});

	const { editedContent, setEditedContent, isDirty, save, isSaving, saveSuccess } = useMarkdownSave(
		{
			endpoint: `/api/reading/digests/${date}`,
			queryKey: ["reading", date],
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
					to="/reading"
					className="text-sm text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"
				>
					&larr; Reading
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
				<span className="text-sm text-zinc-500">
					{data.meta.itemCount} items from {data.meta.sources.length} sources
				</span>
			</div>

			{isEditing ? (
				<MarkdownEditor value={editedContent} onChange={setEditedContent} onSave={save} />
			) : (
				<MarkdownRenderer content={data.content} />
			)}
		</div>
	);
}
