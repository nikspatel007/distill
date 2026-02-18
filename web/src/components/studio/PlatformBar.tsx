import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import type { PlatformContent, PostizIntegration } from "../../../shared/schemas.js";

interface PlatformBarProps {
	slug: string;
	selectedPlatform: string;
	onSelectPlatform: (platform: string) => void;
	platforms: Record<string, PlatformContent>;
}

const PLATFORMS = [
	{
		key: "ghost",
		label: "Ghost",
		color: "bg-purple-100 text-purple-700 dark:bg-purple-950 dark:text-purple-300",
	},
	{
		key: "x",
		label: "X",
		color: "bg-sky-100 text-sky-700 dark:bg-sky-950 dark:text-sky-300",
	},
	{
		key: "linkedin",
		label: "LinkedIn",
		color: "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300",
	},
	{
		key: "slack",
		label: "Slack",
		color: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
	},
];

export function PlatformBar({
	slug,
	selectedPlatform,
	onSelectPlatform,
	platforms,
}: PlatformBarProps) {
	const queryClient = useQueryClient();
	const [publishError, setPublishError] = useState<string | null>(null);

	const { data: integrationsData } = useQuery<{
		integrations: PostizIntegration[];
		configured: boolean;
	}>({
		queryKey: ["studio-platforms"],
		queryFn: async () => {
			const res = await fetch("/api/studio/platforms");
			if (!res.ok) throw new Error("Failed to load platforms");
			return res.json();
		},
	});

	const publishMutation = useMutation({
		mutationFn: async () => {
			const readyPlatforms = Object.entries(platforms)
				.filter(([, p]) => p.content && !p.published)
				.map(([key]) => key);

			const res = await fetch(`/api/studio/publish/${slug}`, {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ platforms: readyPlatforms, mode: "draft" }),
			});
			if (!res.ok) {
				const err = await res.json().catch(() => ({ error: "Unknown error" }));
				throw new Error(err.error || "Publish failed");
			}
			return res.json();
		},
		onSuccess: () => {
			setPublishError(null);
			queryClient.invalidateQueries({ queryKey: ["studio-item", slug] });
		},
		onError: (err: Error) => {
			setPublishError(err.message);
		},
	});

	const readyCount = Object.values(platforms).filter((p) => p.content && !p.published).length;
	const allPublished = Object.values(platforms).every((p) => !p.content || p.published);
	const selectedContent = platforms[selectedPlatform]?.content ?? null;
	const _configured = integrationsData?.configured ?? false;

	return (
		<div className="border-t border-zinc-200 dark:border-zinc-800">
			<div className="flex items-center justify-between px-4 py-3">
				<div className="flex items-center gap-2">
					{PLATFORMS.map((p) => {
						const platformData = platforms[p.key];
						const hasContent = !!platformData?.content;
						const isPublished = !!platformData?.published;
						const isSelected = selectedPlatform === p.key;

						return (
							<button
								key={p.key}
								type="button"
								onClick={() => onSelectPlatform(p.key)}
								className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium transition-all ${
									hasContent
										? p.color
										: "bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400"
								} ${isSelected ? "ring-2 ring-indigo-500 ring-offset-1 dark:ring-offset-zinc-900" : ""}`}
							>
								{isPublished && <span>&#10003;</span>}
								{p.label}
							</button>
						);
					})}
				</div>

				<div className="flex items-center gap-3">
					{publishError && <span className="text-xs text-red-500">{publishError}</span>}
					<button
						type="button"
						onClick={() => publishMutation.mutate()}
						disabled={readyCount === 0 || allPublished || publishMutation.isPending}
						className="rounded-lg bg-indigo-600 px-4 py-1.5 text-xs font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
					>
						{publishMutation.isPending ? "Publishing..." : `Publish All Ready (${readyCount})`}
					</button>
				</div>
			</div>

			{selectedContent && (
				<div className="border-t border-zinc-100 px-4 py-3 dark:border-zinc-800">
					<p className="mb-1 text-xs font-medium text-zinc-500">
						Preview: <span className="capitalize">{selectedPlatform}</span>
					</p>
					<div className="max-h-32 overflow-y-auto rounded-lg bg-zinc-50 p-3 text-sm text-zinc-700 dark:bg-zinc-900 dark:text-zinc-300">
						<p className="whitespace-pre-wrap">{selectedContent}</p>
					</div>
				</div>
			)}
		</div>
	);
}
