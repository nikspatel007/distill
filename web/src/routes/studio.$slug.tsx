import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "@tanstack/react-router";
import { ArrowLeft, ImagePlus, Loader2, PanelRightClose, PanelRightOpen } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import type { ChatMessage, PlatformContent, ReviewItem } from "../../shared/schemas.js";
import { MarkdownRenderer } from "../components/shared/MarkdownRenderer.js";
import { AgentChat } from "../components/studio/AgentChat.js";
import { DEFAULT_TYPE_STYLE, STATUS_STYLES, TYPE_STYLES } from "../components/studio/styles.js";

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

const MOODS = [
	"reflective",
	"energetic",
	"cautionary",
	"triumphant",
	"intimate",
	"technical",
	"playful",
	"somber",
] as const;

const PLATFORM_TABS = [
	{ key: "ghost", label: "Ghost" },
	{ key: "x", label: "X" },
	{ key: "linkedin", label: "LinkedIn" },
	{ key: "slack", label: "Slack" },
];

export default function StudioDetail() {
	const { slug } = useParams({ strict: false });
	const queryClient = useQueryClient();
	const navigate = useNavigate();

	const [rightPanelOpen, setRightPanelOpen] = useState(true);
	const [selectedPlatform, setSelectedPlatform] = useState("ghost");
	const [showPreview, setShowPreview] = useState(false);
	const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
	const [platforms, setPlatforms] = useState<Record<string, PlatformContent>>({});
	const [mobileView, setMobileView] = useState<"content" | "chat">("content");

	// Image generation
	const [showImageForm, setShowImageForm] = useState(false);
	const [imagePrompt, setImagePrompt] = useState("");
	const [imageMood, setImageMood] = useState<(typeof MOODS)[number]>("reflective");
	const promptRef = useRef<HTMLInputElement>(null);

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

	const deleteMutation = useMutation({
		mutationFn: async () => {
			const res = await fetch(`/api/studio/items/${slug}`, { method: "DELETE" });
			if (!res.ok) throw new Error("Failed to delete");
			return res.json();
		},
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["studio-items"] });
			navigate({ to: "/studio" });
		},
	});

	const imageMutation = useMutation({
		mutationFn: async ({ prompt, mood }: { prompt: string; mood: string }) => {
			const res = await fetch(`/api/studio/items/${slug}/image`, {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ prompt, mood }),
			});
			if (!res.ok) {
				const body = await res.json().catch(() => ({ error: "Generation failed" }));
				throw new Error(body.error ?? "Generation failed");
			}
			return res.json();
		},
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["studio-item", slug] });
			setImagePrompt("");
			setShowImageForm(false);
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
		},
		[selectedPlatform],
	);

	const handleImageGenerated = useCallback(
		(_url: string, _alt: string) => {
			queryClient.invalidateQueries({ queryKey: ["studio-item", slug] });
		},
		[queryClient, slug],
	);

	const handleSourceUpdated = useCallback(() => {
		queryClient.invalidateQueries({ queryKey: ["studio-item", slug] });
	}, [queryClient, slug]);

	const handleHistoryChange = useCallback(
		(newHistory: ChatMessage[]) => {
			setChatHistory(newHistory);
			saveChatMutation.mutate(newHistory);
		},
		[saveChatMutation],
	);

	useEffect(() => {
		if (showImageForm) promptRef.current?.focus();
	}, [showImageForm]);

	if (isLoading) {
		return <div className="animate-pulse text-zinc-400">Loading...</div>;
	}
	if (error) {
		return <div className="text-red-500">Error: {error.message}</div>;
	}
	if (!data) return null;

	const selectedContent = platforms[selectedPlatform]?.content ?? null;
	const images = data.images ?? [];
	const heroImage = images.find((img) => img.role === "hero");

	return (
		<div className="flex h-full flex-col">
			{/* Header */}
			<div className="flex flex-col gap-2 border-b border-zinc-200 px-4 py-2.5 dark:border-zinc-800 md:flex-row md:items-center md:justify-between">
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
						onClick={() => {
							if (window.confirm("Delete this content? This cannot be undone."))
								deleteMutation.mutate();
						}}
						disabled={deleteMutation.isPending}
						className="rounded-lg px-3 py-1.5 text-xs font-medium text-red-600 hover:bg-red-50 disabled:opacity-50 dark:text-red-400 dark:hover:bg-red-950/30"
					>
						Delete
					</button>
					<button
						type="button"
						onClick={() => setRightPanelOpen(!rightPanelOpen)}
						className="hidden rounded-lg p-2 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700 dark:hover:bg-zinc-800 dark:hover:text-zinc-200 md:inline-flex"
					>
						{rightPanelOpen ? (
							<PanelRightClose className="h-5 w-5" />
						) : (
							<PanelRightOpen className="h-5 w-5" />
						)}
					</button>
				</div>
			</div>

			{/* Mobile content/chat toggle */}
			<div className="flex border-b border-zinc-200 dark:border-zinc-800 md:hidden">
				<button
					type="button"
					onClick={() => setMobileView("content")}
					className={`flex-1 py-2.5 text-center text-sm font-medium ${mobileView === "content" ? "border-b-2 border-indigo-600 text-indigo-600" : "text-zinc-500"}`}
				>
					Content
				</button>
				<button
					type="button"
					onClick={() => setMobileView("chat")}
					className={`flex-1 py-2.5 text-center text-sm font-medium ${mobileView === "chat" ? "border-b-2 border-indigo-600 text-indigo-600" : "text-zinc-500"}`}
				>
					Chat
				</button>
			</div>

			{/* Main area */}
			<div className="flex min-h-0 flex-1">
				{/* Left: Source content + platforms */}
				<div
					className={`${mobileView === "content" ? "flex" : "hidden"} md:flex flex-col overflow-hidden md:border-r border-zinc-200 dark:border-zinc-800 w-full ${rightPanelOpen ? "md:w-1/2" : "md:w-full"}`}
				>
					<div className="flex-1 overflow-y-auto">
						{/* Hero image */}
						{heroImage && (
							<div className="border-b border-zinc-100 dark:border-zinc-800">
								<img
									src={`/api/studio/images/${heroImage.relative_path}`}
									alt={heroImage.prompt || data.title}
									className="w-full max-h-40 object-cover md:max-h-[280px]"
									onError={(e) => {
										(e.target as HTMLImageElement).style.display = "none";
									}}
								/>
							</div>
						)}

						{/* Image thumbnails + generate button */}
						{(images.length > 0 || true) && (
							<div className="flex items-center gap-2 border-b border-zinc-100 bg-zinc-50 px-4 py-2 md:px-6 dark:border-zinc-800 dark:bg-zinc-900/50">
								{images
									.filter((img) => img !== heroImage)
									.map((img) => (
										<div key={img.filename} className="group relative shrink-0">
											<img
												src={`/api/studio/images/${img.relative_path}`}
												alt={img.role}
												className="h-10 w-auto rounded border border-zinc-200 object-cover dark:border-zinc-700"
												onError={(e) => {
													(e.target as HTMLImageElement).style.display = "none";
												}}
											/>
											<span className="absolute bottom-0 left-0 right-0 rounded-b bg-black/50 px-0.5 text-center text-[9px] text-white">
												{img.role}
											</span>
										</div>
									))}
								<button
									type="button"
									onClick={() => setShowImageForm((v) => !v)}
									className="flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs font-medium text-zinc-500 hover:bg-zinc-100 hover:text-zinc-700 dark:hover:bg-zinc-800 dark:hover:text-zinc-300"
								>
									<ImagePlus className="h-3.5 w-3.5" />
									Generate Image
								</button>
							</div>
						)}

						{/* Image generation form */}
						{showImageForm && (
							<div className="border-b border-zinc-100 bg-zinc-50 px-4 py-3 md:px-6 dark:border-zinc-800 dark:bg-zinc-900/50">
								<form
									onSubmit={(e) => {
										e.preventDefault();
										const trimmed = imagePrompt.trim();
										if (!trimmed || imageMutation.isPending) return;
										imageMutation.mutate({ prompt: trimmed, mood: imageMood });
									}}
									className="flex flex-col gap-2"
								>
									<input
										ref={promptRef}
										type="text"
										value={imagePrompt}
										onChange={(e) => setImagePrompt(e.target.value)}
										placeholder="Describe the visual — a scene, not the article topic"
										disabled={imageMutation.isPending}
										className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm placeholder-zinc-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-900 dark:placeholder-zinc-500"
									/>
									<div className="flex items-center gap-2">
										<select
											value={imageMood}
											onChange={(e) => setImageMood(e.target.value as (typeof MOODS)[number])}
											disabled={imageMutation.isPending}
											className="rounded-lg border border-zinc-300 bg-white px-2 py-1.5 text-xs disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-900"
										>
											{MOODS.map((m) => (
												<option key={m} value={m}>
													{m}
												</option>
											))}
										</select>
										<button
											type="submit"
											disabled={!imagePrompt.trim() || imageMutation.isPending}
											className="flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-700 disabled:opacity-40"
										>
											{imageMutation.isPending ? (
												<>
													<Loader2 className="h-3 w-3 animate-spin" />
													Generating...
												</>
											) : (
												"Generate"
											)}
										</button>
										<button
											type="button"
											onClick={() => setShowImageForm(false)}
											className="px-2 py-1.5 text-xs text-zinc-400 hover:text-zinc-600"
										>
											Cancel
										</button>
									</div>
									{imageMutation.isError && (
										<p className="text-xs text-red-500">{imageMutation.error.message}</p>
									)}
								</form>
							</div>
						)}

						{/* Platform chips */}
						<div className="flex items-center gap-1.5 overflow-x-auto border-b border-zinc-100 px-4 py-2 dark:border-zinc-800 md:px-6">
							{PLATFORM_TABS.map((p) => {
								const hasContent = !!platforms[p.key]?.content;
								const isSelected = selectedPlatform === p.key;
								return (
									<button
										key={p.key}
										type="button"
										onClick={() => {
											if (isSelected) {
												setShowPreview(!showPreview);
											} else {
												setSelectedPlatform(p.key);
												setShowPreview(true);
											}
										}}
										className={`relative rounded-full px-2.5 py-1 text-xs font-medium transition-colors ${
											isSelected
												? "bg-zinc-800 text-white dark:bg-zinc-200 dark:text-zinc-900"
												: hasContent
													? "bg-zinc-100 text-zinc-600 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-400 dark:hover:bg-zinc-700"
													: "text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300"
										}`}
									>
										{p.label}
										{hasContent && !isSelected && (
											<span className="absolute -right-0.5 -top-0.5 h-1.5 w-1.5 rounded-full bg-emerald-500" />
										)}
									</button>
								);
							})}
						</div>

						{/* Collapsible platform preview */}
						{showPreview && (
							<div className="border-b border-zinc-200 dark:border-zinc-800">
								{selectedContent ? (
									<div className="p-4">
										<div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-700 dark:bg-zinc-900">
											<PlatformPreview platform={selectedPlatform} content={selectedContent} />
										</div>
									</div>
								) : (
									<div className="px-4 py-4 text-center md:px-6">
										<p className="text-xs text-zinc-400">
											No {selectedPlatform} content yet — ask the agent to write it.
										</p>
									</div>
								)}
							</div>
						)}

						{/* Source content */}
						<div className="p-4 md:p-6">
							<MarkdownRenderer content={data.content} />
						</div>
					</div>
				</div>

				{/* Right: Chat only */}
				<div
					className={`${mobileView === "chat" ? "flex" : "hidden"} ${rightPanelOpen ? "md:flex" : "md:hidden"} w-full md:w-1/2 md:min-w-[360px] flex-col`}
				>
						<div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
							<AgentChat
								content={data.content}
								platform={selectedPlatform}
								slug={slug ?? ""}
								chatHistory={chatHistory}
								onPlatformContent={handlePlatformContent}
								onImageGenerated={handleImageGenerated}
								onSourceUpdated={handleSourceUpdated}
								onHistoryChange={handleHistoryChange}
							/>
						</div>
					</div>
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
