import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useState } from "react";
import type { PostizIntegration, PublishQueueItem } from "../../shared/schemas.js";
import { DateBadge } from "../components/shared/DateBadge.js";

interface GroupedPost {
	slug: string;
	title: string;
	postType: string;
	date: string;
	platforms: { platform: string; published: boolean }[];
}

function groupBySlug(items: PublishQueueItem[]): GroupedPost[] {
	const map = new Map<string, GroupedPost>();
	for (const item of items) {
		const existing = map.get(item.slug);
		if (existing) {
			existing.platforms.push({ platform: item.platform, published: item.published });
		} else {
			map.set(item.slug, {
				slug: item.slug,
				title: item.title,
				postType: item.postType,
				date: item.date,
				platforms: [{ platform: item.platform, published: item.published }],
			});
		}
	}
	return [...map.values()].sort((a, b) => b.date.localeCompare(a.date));
}

export default function Publish() {
	const queryClient = useQueryClient();
	const [publishing, setPublishing] = useState<string | null>(null);

	const { data, isLoading } = useQuery<{
		queue: PublishQueueItem[];
		postizConfigured: boolean;
	}>({
		queryKey: ["publish-queue"],
		queryFn: async () => {
			const res = await fetch("/api/publish/queue");
			if (!res.ok) throw new Error("Failed to load publish queue");
			return res.json();
		},
	});

	const { data: _integrationsData } = useQuery<{
		integrations: PostizIntegration[];
		configured: boolean;
	}>({
		queryKey: ["integrations"],
		queryFn: async () => {
			const res = await fetch("/api/publish/integrations");
			if (!res.ok) throw new Error("Failed to load integrations");
			return res.json();
		},
	});

	const publishMutation = useMutation({
		mutationFn: async ({
			slug,
			platform,
			mode,
		}: { slug: string; platform: string; mode: string }) => {
			const res = await fetch(`/api/publish/${slug}`, {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ platform, mode }),
			});
			if (!res.ok) {
				const err = await res.json().catch(() => ({ error: "Unknown error" }));
				throw new Error(err.error || "Publish failed");
			}
			return res.json();
		},
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["publish-queue"] });
			setPublishing(null);
		},
		onError: () => setPublishing(null),
	});

	if (isLoading)
		return (
			<div className="mx-auto max-w-5xl p-4 md:p-6">
				<div className="animate-pulse text-zinc-400">Loading publish queue...</div>
			</div>
		);

	const queue = data?.queue ?? [];
	const postizConfigured = data?.postizConfigured ?? false;

	if (postizConfigured) {
		return (
			<div className="mx-auto max-w-5xl p-4 md:p-6">
				<PostizQueueView
					queue={queue}
					publishing={publishing}
					setPublishing={setPublishing}
					publishMutation={publishMutation}
				/>
			</div>
		);
	}

	return (
		<div className="mx-auto max-w-5xl p-4 md:p-6">
			<CardView queue={queue} postizConfigured={postizConfigured} />
		</div>
	);
}

function CardView({
	queue,
	postizConfigured,
}: { queue: PublishQueueItem[]; postizConfigured: boolean }) {
	const grouped = groupBySlug(queue);

	return (
		<div className="space-y-6">
			<h2 className="text-2xl font-bold">Publish</h2>

			{grouped.length === 0 ? (
				<div className="rounded-lg border border-zinc-200 p-8 text-center dark:border-zinc-800">
					<p className="text-zinc-500">
						No blog posts yet. Run{" "}
						<code className="rounded bg-zinc-100 px-1.5 py-0.5 text-xs dark:bg-zinc-800">
							distill blog
						</code>{" "}
						to generate content for publishing.
					</p>
				</div>
			) : (
				<div className="space-y-3">
					{grouped.map((post) => {
						const allPublished = post.platforms.every((p) => p.published);
						const somePublished = post.platforms.some((p) => p.published);

						return (
							<div
								key={post.slug}
								className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800"
							>
								<div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
									<div className="flex min-w-0 items-center gap-2">
										<Link
											to="/blog/$slug"
											params={{ slug: post.slug }}
											className="truncate font-medium hover:text-indigo-600 dark:hover:text-indigo-400"
										>
											{post.title}
										</Link>
										<span
											className={`rounded-full px-2 py-0.5 text-xs font-medium ${
												post.postType === "weekly"
													? "bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300"
													: "bg-green-50 text-green-700 dark:bg-green-950 dark:text-green-300"
											}`}
										>
											{post.postType}
										</span>
									</div>
									<div className="flex items-center gap-2">
										{allPublished && <span className="text-xs text-green-600">Published</span>}
										{somePublished && !allPublished && (
											<span className="text-xs text-amber-600">Partial</span>
										)}
										<DateBadge date={post.date} />
									</div>
								</div>

								<div className="mt-3 flex flex-wrap gap-2">
									{post.platforms.map((p) => (
										<span
											key={p.platform}
											className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${
												p.published
													? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200"
													: "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400"
											}`}
										>
											{p.published && <span>&#10003;</span>}
											{p.platform}
										</span>
									))}
								</div>
							</div>
						);
					})}
				</div>
			)}

			{!postizConfigured && (
				<p className="text-xs text-zinc-400">
					Connect Postiz (set{" "}
					<code className="rounded bg-zinc-100 px-1 py-0.5 dark:bg-zinc-800">POSTIZ_URL</code> and{" "}
					<code className="rounded bg-zinc-100 px-1 py-0.5 dark:bg-zinc-800">POSTIZ_API_KEY</code>)
					to draft and schedule posts directly from here.
				</p>
			)}
		</div>
	);
}

function PostizQueueView({
	queue,
	publishing,
	setPublishing,
	publishMutation,
}: {
	queue: PublishQueueItem[];
	publishing: string | null;
	setPublishing: (v: string | null) => void;
	publishMutation: ReturnType<
		typeof useMutation<unknown, Error, { slug: string; platform: string; mode: string }>
	>;
}) {
	const unpublished = queue.filter((q) => !q.published);
	const published = queue.filter((q) => q.published);

	return (
		<div className="space-y-6">
			<h2 className="text-2xl font-bold">Publish Queue</h2>

			<section>
				<h3 className="mb-3 text-lg font-semibold">Ready to Publish ({unpublished.length})</h3>
				{unpublished.length === 0 ? (
					<p className="text-sm text-zinc-500">All posts published!</p>
				) : (
					<div className="overflow-x-auto">
						<table className="w-full min-w-[500px] text-left text-sm">
							<thead className="border-b border-zinc-200 dark:border-zinc-800">
								<tr>
									<th className="pb-2 font-medium">Post</th>
									<th className="pb-2 font-medium">Type</th>
									<th className="pb-2 font-medium">Platform</th>
									<th className="pb-2 font-medium">Action</th>
								</tr>
							</thead>
							<tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
								{unpublished.map((item) => {
									const key = `${item.slug}-${item.platform}`;
									return (
										<tr key={key}>
											<td className="py-2">
												<Link
													to="/blog/$slug"
													params={{ slug: item.slug }}
													className="hover:text-indigo-600 dark:hover:text-indigo-400"
												>
													{item.title}
												</Link>
											</td>
											<td className="py-2">{item.postType}</td>
											<td className="py-2">
												<span className="rounded-full bg-zinc-100 px-2 py-0.5 text-xs dark:bg-zinc-800">
													{item.platform}
												</span>
											</td>
											<td className="py-2">
												<button
													type="button"
													onClick={() => {
														setPublishing(key);
														publishMutation.mutate({
															slug: item.slug,
															platform: item.platform,
															mode: "draft",
														});
													}}
													disabled={publishing === key}
													className="rounded bg-indigo-600 px-3 py-2 text-xs text-white hover:bg-indigo-700 disabled:opacity-50"
												>
													{publishing === key ? "Publishing..." : "Draft"}
												</button>
											</td>
										</tr>
									);
								})}
							</tbody>
						</table>
					</div>
				)}
			</section>

			{published.length > 0 && (
				<section>
					<h3 className="mb-3 text-lg font-semibold">Published ({published.length})</h3>
					<div className="space-y-1">
						{published.map((item) => (
							<div
								key={`${item.slug}-${item.platform}`}
								className="flex items-center gap-2 text-sm text-zinc-500"
							>
								<span className="text-green-600">&#10003;</span>
								<Link
									to="/blog/$slug"
									params={{ slug: item.slug }}
									className="hover:text-indigo-600 dark:hover:text-indigo-400"
								>
									{item.title}
								</Link>
								<span className="rounded-full bg-green-100 px-2 py-0.5 text-xs text-green-800 dark:bg-green-900 dark:text-green-200">
									{item.platform}
								</span>
							</div>
						))}
					</div>
				</section>
			)}
		</div>
	);
}
