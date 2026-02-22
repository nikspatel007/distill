import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "@tanstack/react-router";
import { useState } from "react";
import type { BlogDetail } from "../../shared/schemas.js";
import { DateBadge } from "../components/shared/DateBadge.js";
import { EditToggle } from "../components/shared/EditToggle.js";
import { MarkdownEditor } from "../components/shared/MarkdownEditor.js";
import { MarkdownRenderer } from "../components/shared/MarkdownRenderer.js";
import { useMarkdownSave } from "../lib/useMarkdownSave.js";

export default function BlogDetailPage() {
	const { slug } = useParams({ from: "/blog/$slug" });
	const [isEditing, setIsEditing] = useState(false);
	const { data, isLoading, error } = useQuery<BlogDetail>({
		queryKey: ["blog", slug],
		queryFn: async () => {
			const res = await fetch(`/api/blog/posts/${slug}`);
			if (!res.ok) throw new Error("Blog post not found");
			return res.json();
		},
	});

	const { editedContent, setEditedContent, isDirty, save, isSaving, saveSuccess } = useMarkdownSave(
		{
			endpoint: `/api/blog/posts/${slug}`,
			queryKey: ["blog", slug],
			originalContent: data?.content ?? "",
		},
	);

	if (isLoading)
		return (
			<div className="mx-auto max-w-5xl p-4 md:p-6">
				<div className="animate-pulse text-zinc-400">Loading...</div>
			</div>
		);
	if (error)
		return (
			<div className="mx-auto max-w-5xl p-4 md:p-6">
				<div className="text-red-500">Error: {error.message}</div>
			</div>
		);
	if (!data) return null;

	const heroImage = data.images.find((img) => img.role === "hero");

	return (
		<div className="mx-auto max-w-5xl p-4 md:p-6">
			<div className="space-y-4">
				<div className="flex items-center justify-between">
					<Link
						to="/blog"
						className="text-sm text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"
					>
						&larr; Blog
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

				{heroImage && (
					<img
						src={`/api/studio/images/${heroImage.relative_path}`}
						alt={heroImage.prompt || data.meta.title}
						className="w-full max-h-48 rounded-xl object-cover sm:max-h-64 md:max-h-[400px]"
					/>
				)}

				<div>
					<h2 className="text-xl font-bold md:text-2xl">{data.meta.title}</h2>
					<div className="mt-2 flex items-center gap-2">
						<DateBadge date={data.meta.date} />
						<span
							className={`rounded-full px-2 py-0.5 text-xs font-medium ${
								data.meta.postType === "weekly"
									? "bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300"
									: "bg-green-50 text-green-700 dark:bg-green-950 dark:text-green-300"
							}`}
						>
							{data.meta.postType}
						</span>
					</div>
				</div>

				{isEditing ? (
					<MarkdownEditor value={editedContent} onChange={setEditedContent} onSave={save} />
				) : (
					<MarkdownRenderer content={data.content} />
				)}
			</div>
		</div>
	);
}
