import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "@tanstack/react-router";
import { ArrowLeft, Image, PanelRightClose, PanelRightOpen } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import type { ChatMessage, PlatformContent, ReviewItem } from "../../shared/schemas.js";
import { MarkdownRenderer } from "../components/shared/MarkdownRenderer.js";
import { AgentChat } from "../components/studio/AgentChat.js";
import { PlatformBar } from "../components/studio/PlatformBar.js";

interface ContentStoreImage {
	filename: string;
	role: string;
	prompt: string;
	relative_path: string;
}

interface StudioItemResponse {
	slug: string;
	title: string;
	type: string;
	content: string;
	frontmatter: Record<string, unknown>;
	review: ReviewItem;
	content_store?: boolean;
	store_status?: string;
	images?: ContentStoreImage[];
}

const TYPE_STYLES: Record<string, string> = {
	weekly: "bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300",
	thematic: "bg-purple-50 text-purple-700 dark:bg-purple-950 dark:text-purple-300",
	digest: "bg-orange-50 text-orange-700 dark:bg-orange-950 dark:text-orange-300",
	"daily-social": "bg-pink-50 text-pink-700 dark:bg-pink-950 dark:text-pink-300",
	daily_social: "bg-pink-50 text-pink-700 dark:bg-pink-950 dark:text-pink-300",
	seed: "bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
	reading_list: "bg-teal-50 text-teal-700 dark:bg-teal-950 dark:text-teal-300",
};
const DEFAULT_TYPE_STYLE = "bg-zinc-50 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400";

const STATUS_STYLES: Record<string, string> = {
	draft: "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400",
	review: "bg-indigo-50 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300",
	ready: "bg-amber-50 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
	published: "bg-green-50 text-green-700 dark:bg-green-950 dark:text-green-300",
	archived: "bg-zinc-50 text-zinc-400 dark:bg-zinc-900 dark:text-zinc-500",
};

export default function StudioDetail() {
	const { slug } = useParams({ strict: false });
	const queryClient = useQueryClient();

	const [rightPanelOpen, setRightPanelOpen] = useState(true);
	const [selectedPlatform, setSelectedPlatform] = useState("ghost");
	const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
	const [platforms, setPlatforms] = useState<Record<string, PlatformContent>>({});

	const { data, isLoading, error } = useQuery<StudioItemResponse>({
		queryKey: ["studio-item", slug],
		queryFn: async () => {
			const res = await fetch(`/api/studio/items/${slug}`);
			if (!res.ok) throw new Error("Content not found");
			return res.json();
		},
		enabled: !!slug,
	});

	useEffect(() => {
		if (data?.review) {
			setChatHistory(data.review.chat_history);
			setPlatforms(data.review.platforms);
		}
	}, [data?.review]);

	const saveChatMutation = useMutation({
		mutationFn: async (history: ChatMessage[]) => {
			const res = await fetch(`/api/studio/items/${slug}/chat`, {
				method: "PUT",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ chat_history: history }),
			});
			if (!res.ok) throw new Error("Failed to save chat history");
			return res.json();
		},
	});

	const _savePlatformMutation = useMutation({
		mutationFn: async ({ platform, content }: { platform: string; content: string }) => {
			const res = await fetch(`/api/studio/items/${slug}/platform/${platform}`, {
				method: "PUT",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ content }),
			});
			if (!res.ok) throw new Error("Failed to save platform content");
			return res.json();
		},
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["studio-item", slug] });
		},
	});

	const statusMutation = useMutation({
		mutationFn: async (newStatus: string) => {
			const res = await fetch(`/api/studio/items/${slug}/status`, {
				method: "PUT",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ status: newStatus }),
			});
			if (!res.ok) throw new Error("Failed to update status");
			return res.json();
		},
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["studio-item", slug] });
			queryClient.invalidateQueries({ queryKey: ["studio-items"] });
		},
	});

	const currentStatus = data?.store_status ?? data?.review.status ?? "draft";

	const handlePlatformContent = useCallback(
		(adaptedContent: string) => {
			setPlatforms((prev) => ({
				...prev,
				[selectedPlatform]: {
					enabled: true,
					content: adaptedContent,
					published: false,
					postiz_id: null,
					...((prev[selectedPlatform]?.published ? { published: true } : {}) as Record<
						string,
						never
					>),
				},
			}));
			// Tool already saved to content store on the server side
		},
		[selectedPlatform],
	);

	const handleImageGenerated = useCallback(
		(_url: string, _alt: string) => {
			queryClient.invalidateQueries({ queryKey: ["studio-item", slug] });
		},
		[queryClient, slug],
	);

	const handleHistoryChange = useCallback(
		(newHistory: ChatMessage[]) => {
			setChatHistory(newHistory);
			saveChatMutation.mutate(newHistory);
		},
		[saveChatMutation],
	);

	if (isLoading) {
		return <div className="animate-pulse text-zinc-400">Loading...</div>;
	}
	if (error) {
		return <div className="text-red-500">Error: {error.message}</div>;
	}
	if (!data) return null;

	const selectedContent = platforms[selectedPlatform]?.content ?? null;
	const images = data.images ?? [];

	return (
		<div className="-mx-6 -mt-6 flex h-[calc(100vh-3rem)] flex-col">
			{/* Header */}
			<div className="flex items-center justify-between border-b border-zinc-200 px-4 py-2.5 dark:border-zinc-800">
				<div className="flex items-center gap-3">
					<Link to="/studio" className="text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200">
						<ArrowLeft className="h-5 w-5" />
					</Link>
					<div className="flex items-center gap-2.5">
						<h1 className="text-base font-bold">{data.title}</h1>
						<span
							className={`rounded-full px-2 py-0.5 text-xs font-medium ${TYPE_STYLES[data.type] ?? DEFAULT_TYPE_STYLE}`}
						>
							{data.type.replace("_", " ")}
						</span>
						<span
							className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[currentStatus] ?? "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400"}`}
						>
							{currentStatus}
						</span>
					</div>
				</div>
				<div className="flex items-center gap-2">
					{currentStatus === "draft" && (
						<button
							type="button"
							onClick={() => statusMutation.mutate("review")}
							disabled={statusMutation.isPending}
							className="rounded-lg bg-indigo-100 px-3 py-1.5 text-xs font-medium text-indigo-700 hover:bg-indigo-200 disabled:opacity-50 dark:bg-indigo-950 dark:text-indigo-300 dark:hover:bg-indigo-900"
						>
							Mark for Review
						</button>
					)}
					{currentStatus === "review" && (
						<button
							type="button"
							onClick={() => statusMutation.mutate("ready")}
							disabled={statusMutation.isPending}
							className="rounded-lg bg-amber-100 px-3 py-1.5 text-xs font-medium text-amber-700 hover:bg-amber-200 disabled:opacity-50 dark:bg-amber-950 dark:text-amber-300 dark:hover:bg-amber-900"
						>
							Approve
						</button>
					)}
					<button
						type="button"
						onClick={() => setRightPanelOpen(!rightPanelOpen)}
						className="rounded-lg p-2 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700 dark:hover:bg-zinc-800 dark:hover:text-zinc-200"
					>
						{rightPanelOpen ? (
							<PanelRightClose className="h-5 w-5" />
						) : (
							<PanelRightOpen className="h-5 w-5" />
						)}
					</button>
				</div>
			</div>

			{/* Main area */}
			<div className="flex min-h-0 flex-1">
				{/* Left: Source content */}
				<div
					className={`overflow-y-auto border-r border-zinc-200 dark:border-zinc-800 ${rightPanelOpen ? "w-1/2" : "w-full"}`}
				>
					{/* Images strip */}
					{images.length > 0 && (
						<div className="border-b border-zinc-100 bg-zinc-50 px-6 py-3 dark:border-zinc-800 dark:bg-zinc-900/50">
							<div className="flex items-center gap-2 overflow-x-auto">
								<Image className="h-4 w-4 shrink-0 text-zinc-400" />
								{images.map((img) => (
									<div key={img.filename} className="group relative shrink-0">
										<img
											src={`/api/studio/images/${img.relative_path}`}
											alt={img.role}
											className="h-16 w-auto rounded-md border border-zinc-200 object-cover dark:border-zinc-700"
											onError={(e) => {
												(e.target as HTMLImageElement).style.display = "none";
											}}
										/>
										<span className="absolute bottom-0 left-0 right-0 rounded-b-md bg-black/50 px-1 py-0.5 text-center text-[10px] text-white">
											{img.role}
										</span>
									</div>
								))}
							</div>
						</div>
					)}

					<div className="p-6">
						<MarkdownRenderer content={data.content} />
					</div>
				</div>

				{/* Right: Platform content + Chat (continuous) */}
				{rightPanelOpen && (
					<div className="flex w-1/2 min-w-[360px] flex-col">
						{/* Platform tabs */}
						<PlatformBar
							slug={slug ?? ""}
							selectedPlatform={selectedPlatform}
							onSelectPlatform={setSelectedPlatform}
							platforms={platforms}
						/>

						{/* Scrollable: platform preview + chat */}
						<div className="flex-1 overflow-y-auto">
							{/* Platform content preview */}
							{selectedContent ? (
								<div className="border-b border-zinc-100 px-4 py-4 dark:border-zinc-800">
									<div className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-700 dark:bg-zinc-900">
										<PlatformPreview platform={selectedPlatform} content={selectedContent} />
									</div>
								</div>
							) : (
								<div className="border-b border-zinc-100 px-4 py-6 text-center dark:border-zinc-800">
									<p className="text-sm text-zinc-500">
										No <span className="font-medium capitalize">{selectedPlatform}</span> content
										yet.
									</p>
									<p className="mt-2 text-xs text-zinc-400">
										Try: &quot;Write a {selectedPlatform === "x" ? "thread" : "post"} about the most
										interesting thing from these notes&quot;
									</p>
								</div>
							)}

							{/* Chat (continuous below content) */}
							<AgentChat
								content={data.content}
								platform={selectedPlatform}
								slug={slug ?? ""}
								chatHistory={chatHistory}
								onPlatformContent={handlePlatformContent}
								onImageGenerated={handleImageGenerated}
								onHistoryChange={handleHistoryChange}
							/>
						</div>
					</div>
				)}
			</div>
		</div>
	);
}

/** Renders platform content with platform-appropriate styling. */
function PlatformPreview({ platform, content }: { platform: string; content: string }) {
	if (platform === "x") {
		// Split tweets by --- separator
		const tweets = content
			.split(/\n---\n/)
			.map((t) => t.trim())
			.filter(Boolean);
		return (
			<div className="space-y-3">
				{tweets.map((tweet, i) => (
					<div key={tweet.slice(0, 40)} className="relative">
						{i > 0 && (
							<div className="absolute -top-3 left-4 h-3 w-px bg-zinc-300 dark:bg-zinc-600" />
						)}
						<div className="flex gap-3">
							<div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-zinc-200 text-xs font-bold text-zinc-500 dark:bg-zinc-700 dark:text-zinc-400">
								{i + 1}
							</div>
							<div className="flex-1">
								<p className="text-sm leading-relaxed text-zinc-800 dark:text-zinc-200">{tweet}</p>
								<p
									className={`mt-1 text-xs ${tweet.length > 280 ? "font-medium text-red-500" : "text-zinc-400"}`}
								>
									{tweet.length}/280
								</p>
							</div>
						</div>
					</div>
				))}
			</div>
		);
	}

	if (platform === "linkedin") {
		return (
			<div className="space-y-2">
				<div className="flex items-center gap-2 pb-2">
					<div className="h-8 w-8 rounded-full bg-blue-100 dark:bg-blue-900" />
					<div>
						<p className="text-xs font-semibold text-zinc-700 dark:text-zinc-300">You</p>
						<p className="text-[10px] text-zinc-400">Just now</p>
					</div>
				</div>
				<p className="whitespace-pre-wrap text-sm leading-relaxed text-zinc-800 dark:text-zinc-200">
					{content}
				</p>
				<p
					className={`text-xs ${content.length > 3000 ? "font-medium text-red-500" : "text-zinc-400"}`}
				>
					{content.length.toLocaleString()} chars
				</p>
			</div>
		);
	}

	if (platform === "slack") {
		return (
			<div className="space-y-1">
				<div className="flex items-center gap-1.5 pb-1">
					<div className="h-5 w-5 rounded bg-emerald-200 dark:bg-emerald-800" />
					<span className="text-xs font-bold text-zinc-700 dark:text-zinc-300">Distill Bot</span>
					<span className="text-[10px] text-zinc-400">today</span>
				</div>
				<p className="whitespace-pre-wrap font-mono text-sm leading-relaxed text-zinc-800 dark:text-zinc-200">
					{content}
				</p>
			</div>
		);
	}

	// Ghost / default: render as markdown
	return (
		<div className="prose prose-sm prose-zinc dark:prose-invert max-w-none">
			<MarkdownRenderer content={content} />
		</div>
	);
}
