import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import type { PostizIntegration, PublishQueueItem } from "../../shared/schemas.js";

export default function Publish() {
	const queryClient = useQueryClient();
	const [publishing, setPublishing] = useState<string | null>(null);

	const { data } = useQuery<{ queue: PublishQueueItem[]; postizConfigured: boolean }>({
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

	const queue = data?.queue ?? [];
	const unpublished = queue.filter((q) => !q.published);
	const published = queue.filter((q) => q.published);

	return (
		<div className="space-y-6">
			<h2 className="text-2xl font-bold">Publish Queue</h2>

			{!data?.postizConfigured && (
				<div className="rounded-lg bg-amber-50 p-4 text-sm text-amber-800 dark:bg-amber-950 dark:text-amber-200">
					Postiz is not configured. Set POSTIZ_URL and POSTIZ_API_KEY environment variables.
				</div>
			)}

			{/* Unpublished */}
			<section>
				<h3 className="mb-3 text-lg font-semibold">Ready to Publish ({unpublished.length})</h3>
				{unpublished.length === 0 ? (
					<p className="text-sm text-zinc-500">All posts published!</p>
				) : (
					<div className="overflow-x-auto">
						<table className="w-full text-left text-sm">
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
											<td className="py-2">{item.title}</td>
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
													disabled={publishing === key || !data?.postizConfigured}
													className="rounded bg-indigo-600 px-3 py-1 text-xs text-white hover:bg-indigo-700 disabled:opacity-50"
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

			{/* Published */}
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
								<span>{item.title}</span>
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
