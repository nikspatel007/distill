import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "@tanstack/react-router";
import {
	ArrowLeft,
	Calendar,
	Check,
	ExternalLink,
	ImagePlus,
	Loader2,
	PanelRightClose,
	PanelRightOpen,
	Trash2,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
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

interface GhostTarget {
	name: string;
	label: string;
	configured: boolean;
}

interface PostizIntegration {
	id: string;
	name: string;
	provider: string;
	identifier: string;
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

const CONTENT_TABS = [
	{ key: "source", label: "Source" },
	{ key: "ghost", label: "Ghost" },
	{ key: "x", label: "X" },
	{ key: "linkedin", label: "LinkedIn" },
	{ key: "reddit", label: "Reddit" },
	{ key: "slack", label: "Slack" },
];

/** Map Postiz provider identifiers to our canonical platform keys + display labels. */
const PROVIDER_PLATFORM_MAP: Record<string, { key: string; label: string }> = {
	x: { key: "x", label: "X" },
	twitter: { key: "x", label: "X" },
	linkedin: { key: "linkedin", label: "LinkedIn" },
	"linkedin-page": { key: "linkedin", label: "LinkedIn" },
	"linkedin-profile": { key: "linkedin", label: "LinkedIn" },
	slack: { key: "slack", label: "Slack" },
	reddit: { key: "reddit", label: "Reddit" },
	bluesky: { key: "bluesky", label: "Bluesky" },
	mastodon: { key: "mastodon", label: "Mastodon" },
};

function normalizePlatform(provider: string): { key: string; label: string } {
	const match = PROVIDER_PLATFORM_MAP[provider];
	if (match) return match;
	// Fallback: try prefix match (e.g., "linkedin-company" → "linkedin")
	for (const [prefix, val] of Object.entries(PROVIDER_PLATFORM_MAP)) {
		if (provider.startsWith(prefix)) return val;
	}
	return { key: provider, label: provider };
}

/** Get tomorrow at 9am CT as default schedule time. */
function defaultScheduleTime(): string {
	const d = new Date();
	d.setDate(d.getDate() + 1);
	d.setHours(9, 0, 0, 0);
	// Format as local datetime-local input value
	const pad = (n: number) => n.toString().padStart(2, "0");
	return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export default function StudioDetail() {
	const { slug } = useParams({ strict: false });
	const queryClient = useQueryClient();
	const navigate = useNavigate();

	const [rightPanelOpen, setRightPanelOpen] = useState(true);
	const [selectedTab, setSelectedTab] = useState("source");
	const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
	const [platforms, setPlatforms] = useState<Record<string, PlatformContent>>({});
	const [mobileView, setMobileView] = useState<"content" | "publish" | "chat">("content");

	// Ghost publish state
	const [ghostStatuses, setGhostStatuses] = useState<Record<string, "draft" | "published">>({});

	// Social publish state
	const [socialModes, setSocialModes] = useState<Record<string, "draft" | "schedule" | "now">>({});
	const [scheduleTimes, setScheduleTimes] = useState<Record<string, string>>({});

	// Image generation
	const [imageMood, setImageMood] = useState<(typeof MOODS)[number]>("reflective");

	const { data, isLoading, error } = useQuery<StudioItemResponse>({
		queryKey: ["studio-item", slug],
		queryFn: async () => {
			const res = await fetch(`/api/studio/items/${slug}`);
			if (!res.ok) throw new Error("Content not found");
			return res.json();
		},
		enabled: !!slug,
	});

	// Fetch Ghost targets
	const { data: ghostData } = useQuery<{ targets: GhostTarget[] }>({
		queryKey: ["ghost-targets"],
		queryFn: async () => {
			const res = await fetch("/api/ghost/targets");
			if (!res.ok) return { targets: [] };
			return res.json();
		},
	});

	// Fetch Postiz integrations
	const { data: postizData } = useQuery<{
		integrations: PostizIntegration[];
		configured: boolean;
	}>({
		queryKey: ["studio-platforms"],
		queryFn: async () => {
			const res = await fetch("/api/studio/platforms");
			if (!res.ok) return { integrations: [], configured: false };
			return res.json();
		},
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

	// Ghost publish mutation
	const ghostPublishMutation = useMutation({
		mutationFn: async ({ target, status }: { target: string; status: "draft" | "published" }) => {
			const res = await fetch(`/api/ghost/publish/${slug}`, {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ target, status, tags: [] }),
			});
			if (!res.ok) {
				const body = await res.json().catch(() => ({ error: "Publish failed" }));
				throw new Error(body.error ?? "Publish failed");
			}
			return res.json();
		},
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["studio-item", slug] });
		},
	});

	// Social publish mutation (Postiz)
	const socialPublishMutation = useMutation({
		mutationFn: async ({
			platform,
			mode,
			scheduledAt,
		}: { platform: string; mode: string; scheduledAt?: string }) => {
			const res = await fetch(`/api/studio/publish/${slug}`, {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					platforms: [platform],
					mode,
					scheduled_at: scheduledAt,
				}),
			});
			if (!res.ok) {
				const body = await res.json().catch(() => ({ error: "Publish failed" }));
				throw new Error(body.error ?? "Publish failed");
			}
			return res.json();
		},
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["studio-item", slug] });
		},
	});

	// Batch image mutation
	const batchImageMutation = useMutation({
		mutationFn: async (mood: string) => {
			const res = await fetch(`/api/studio/items/${slug}/images/batch`, {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ mood }),
			});
			if (!res.ok) {
				const body = await res.json().catch(() => ({ error: "Generation failed" }));
				throw new Error(body.error ?? "Generation failed");
			}
			return res.json();
		},
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["studio-item", slug] });
		},
	});

	// The chat platform context: when on "source" tab, default to "ghost" for chat
	const chatPlatform = selectedTab === "source" ? "ghost" : selectedTab;

	const handlePlatformContent = useCallback(
		(adaptedContent: string) => {
			setPlatforms((prev) => ({
				...prev,
				[chatPlatform]: {
					enabled: true,
					content: adaptedContent,
					published: false,
					postiz_id: null,
					...((prev[chatPlatform]?.published ? { published: true } : {}) as Record<string, never>),
				},
			}));
		},
		[chatPlatform],
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

	if (isLoading) {
		return <div className="animate-pulse text-zinc-400 p-6">Loading...</div>;
	}
	if (error) {
		return <div className="text-red-500 p-6">Error: {error.message}</div>;
	}
	if (!data) return null;

	const currentStatus = data.store_status ?? data.review.status ?? "draft";
	const images = data.images ?? [];
	const heroImage = images.find((img) => img.role === "hero");
	const ghostTargets = ghostData?.targets?.filter((t) => t.configured) ?? [];
	const postizIntegrations = postizData?.integrations ?? [];

	// Content for the currently selected tab (null for "source" — shows raw markdown)
	const selectedTabContent =
		selectedTab === "source" ? null : (platforms[selectedTab]?.content ?? null);

	/** Check if a Ghost target has already been published. */
	function isGhostPublished(targetName: string): boolean {
		const key = `ghost_${targetName}`;
		return platforms[key]?.published === true;
	}

	/** Check if a social platform has been published. */
	function isSocialPublished(platform: string): boolean {
		return platforms[platform]?.published === true;
	}

	/** Convert local datetime-local value to ISO 8601 for API. */
	function toISO(localDatetime: string): string {
		return new Date(localDatetime).toISOString();
	}

	return (
		<div className="flex h-full flex-col">
			{/* Header */}
			<div className="flex flex-col gap-2 border-b border-zinc-200 px-4 py-2.5 pt-[max(0.625rem,env(safe-area-inset-top))] dark:border-zinc-800 md:flex-row md:items-center md:justify-between">
				<div className="flex items-center gap-3">
					<Link
						to="/studio"
						className="-ml-2 rounded-lg p-2 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700 dark:hover:bg-zinc-800 dark:hover:text-zinc-200"
					>
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
					<button
						type="button"
						onClick={() => {
							if (window.confirm("Delete this content? This cannot be undone."))
								deleteMutation.mutate();
						}}
						disabled={deleteMutation.isPending}
						className="flex items-center gap-1 rounded-lg px-3 py-1.5 text-xs font-medium text-red-600 hover:bg-red-50 disabled:opacity-50 dark:text-red-400 dark:hover:bg-red-950/30"
					>
						<Trash2 className="h-3.5 w-3.5" />
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

			{/* Mobile tabs */}
			<div className="flex border-b border-zinc-200 dark:border-zinc-800 md:hidden">
				{(["content", "publish", "chat"] as const).map((tab) => (
					<button
						key={tab}
						type="button"
						onClick={() => setMobileView(tab)}
						className={`flex-1 py-2.5 text-center text-sm font-medium capitalize ${mobileView === tab ? "border-b-2 border-indigo-600 text-indigo-600" : "text-zinc-500"}`}
					>
						{tab}
					</button>
				))}
			</div>

			{/* Main area */}
			<div className="flex min-h-0 flex-1">
				{/* Left: Source content + images */}
				<div
					className={`${mobileView === "content" ? "flex" : "hidden"} md:flex flex-col overflow-hidden md:border-r border-zinc-200 dark:border-zinc-800 w-full ${rightPanelOpen ? "md:w-1/2" : "md:w-full"}`}
				>
					<div className="flex-1 flex flex-col overflow-hidden">
						{/* Content tabs: Source + platform tabs */}
						<div className="flex items-center gap-0.5 overflow-x-auto border-b border-zinc-200 px-3 dark:border-zinc-800">
							{CONTENT_TABS.map((tab) => {
								const isSource = tab.key === "source";
								const hasContent = !isSource && !!platforms[tab.key]?.content;
								const isActive = selectedTab === tab.key;
								return (
									<button
										key={tab.key}
										type="button"
										onClick={() => setSelectedTab(tab.key)}
										className={`relative whitespace-nowrap border-b-2 px-3 py-2 text-xs font-medium transition-colors ${
											isActive
												? "border-indigo-600 text-indigo-600 dark:border-indigo-400 dark:text-indigo-400"
												: hasContent
													? "border-transparent text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-200"
													: "border-transparent text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300"
										}`}
									>
										{tab.label}
										{hasContent && !isActive && (
											<span className="absolute right-1 top-1.5 h-1.5 w-1.5 rounded-full bg-emerald-500" />
										)}
									</button>
								);
							})}
						</div>

						{/* Tab content */}
						<div className="flex-1 overflow-y-auto">
							{selectedTab === "source" ? (
								<>
									{/* Hero image (only on source tab) */}
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
									<div className="p-4 md:p-6">
										<MarkdownRenderer content={data.content} />
									</div>
								</>
							) : selectedTabContent ? (
								<div className="p-4 md:p-6">
									<PlatformPreview platform={selectedTab} content={selectedTabContent} />
								</div>
							) : (
								<div className="flex flex-1 items-center justify-center p-8">
									<p className="text-sm text-zinc-400">
										No {selectedTab} content yet — use the chat to generate it.
									</p>
								</div>
							)}
						</div>
					</div>
				</div>

				{/* Right: Publish panel + Chat (stacked) */}
				<div
					className={`${mobileView !== "content" ? "flex" : "hidden"} ${rightPanelOpen ? "md:flex" : "md:hidden"} w-full md:w-1/2 md:min-w-[360px] flex-col`}
				>
					{/* Publish panel */}
					<div
						className={`${mobileView === "publish" || mobileView === "content" ? "" : "hidden md:block"} shrink-0 overflow-y-auto border-b border-zinc-200 dark:border-zinc-800`}
					>
						<div className="space-y-4 p-4">
							<h2 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">Publish</h2>

							{/* Ghost section */}
							{ghostTargets.length > 0 && (
								<div className="space-y-2">
									<h3 className="text-xs font-medium uppercase tracking-wider text-zinc-400">
										Ghost
									</h3>
									{ghostTargets.map((target) => {
										const published = isGhostPublished(target.name);
										const status = ghostStatuses[target.name] ?? "draft";
										return (
											<div key={target.name} className="flex items-center gap-2">
												<span className="flex-1 text-sm text-zinc-700 dark:text-zinc-300">
													{target.label}
												</span>
												{published ? (
													<span className="flex items-center gap-1 text-xs font-medium text-green-600 dark:text-green-400">
														<Check className="h-3.5 w-3.5" />
														Published
													</span>
												) : (
													<>
														<select
															value={status}
															onChange={(e) =>
																setGhostStatuses((prev) => ({
																	...prev,
																	[target.name]: e.target.value as "draft" | "published",
																}))
															}
															className="rounded border border-zinc-300 bg-white px-2 py-1 text-xs dark:border-zinc-700 dark:bg-zinc-900"
														>
															<option value="draft">Draft</option>
															<option value="published">Published</option>
														</select>
														<button
															type="button"
															onClick={() =>
																ghostPublishMutation.mutate({
																	target: target.name,
																	status,
																})
															}
															disabled={ghostPublishMutation.isPending}
															className="flex items-center gap-1 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-700 disabled:opacity-40"
														>
															{ghostPublishMutation.isPending ? (
																<Loader2 className="h-3 w-3 animate-spin" />
															) : (
																<ExternalLink className="h-3 w-3" />
															)}
															Publish
														</button>
													</>
												)}
											</div>
										);
									})}
									{ghostPublishMutation.isError && (
										<p className="text-xs text-red-500">{ghostPublishMutation.error.message}</p>
									)}
								</div>
							)}

							{/* Social section */}
							{postizIntegrations.length > 0 && (
								<div className="space-y-2">
									<h3 className="text-xs font-medium uppercase tracking-wider text-zinc-400">
										Social
									</h3>
									{postizIntegrations.map((integration) => {
										const { key: platformKey, label: platformLabel } = normalizePlatform(
											integration.provider,
										);
										const published = isSocialPublished(platformKey);
										const mode = socialModes[platformKey] ?? "draft";
										const hasContent = !!platforms[platformKey]?.content;
										const scheduleTime = scheduleTimes[platformKey] ?? defaultScheduleTime();

										return (
											<div key={integration.id} className="space-y-1.5">
												<div className="flex items-center gap-2">
													<span className="flex flex-1 items-center gap-1.5 text-sm text-zinc-700 dark:text-zinc-300">
														<span className="font-medium">{platformLabel}</span>
														{integration.name && (
															<span className="text-xs text-zinc-400">{integration.name}</span>
														)}
														{hasContent && (
															<span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
														)}
													</span>
													{published ? (
														<span className="flex items-center gap-1 text-xs font-medium text-green-600 dark:text-green-400">
															<Check className="h-3.5 w-3.5" />
															Published
														</span>
													) : (
														<>
															<select
																value={mode}
																onChange={(e) =>
																	setSocialModes((prev) => ({
																		...prev,
																		[platformKey]: e.target.value as "draft" | "schedule" | "now",
																	}))
																}
																className="rounded border border-zinc-300 bg-white px-2 py-1 text-xs dark:border-zinc-700 dark:bg-zinc-900"
															>
																<option value="draft">Draft</option>
																<option value="schedule">Schedule</option>
																<option value="now">Now</option>
															</select>
															<button
																type="button"
																onClick={() => {
																	const scheduledAt =
																		mode === "schedule" ? toISO(scheduleTime) : undefined;
																	socialPublishMutation.mutate({
																		platform: platformKey,
																		mode,
																		scheduledAt,
																	});
																}}
																disabled={socialPublishMutation.isPending || !hasContent}
																className="flex items-center gap-1 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-700 disabled:opacity-40"
																title={hasContent ? "" : "Generate content first via chat"}
															>
																{socialPublishMutation.isPending ? (
																	<Loader2 className="h-3 w-3 animate-spin" />
																) : (
																	<ExternalLink className="h-3 w-3" />
																)}
																Publish
															</button>
														</>
													)}
												</div>
												{/* Schedule time picker */}
												{mode === "schedule" && !published && (
													<div className="ml-5 flex items-center gap-2">
														<Calendar className="h-3.5 w-3.5 text-zinc-400" />
														<input
															type="datetime-local"
															value={scheduleTime}
															onChange={(e) =>
																setScheduleTimes((prev) => ({
																	...prev,
																	[platformKey]: e.target.value,
																}))
															}
															className="rounded border border-zinc-300 bg-white px-2 py-1 text-xs dark:border-zinc-700 dark:bg-zinc-900"
														/>
													</div>
												)}
											</div>
										);
									})}
									{socialPublishMutation.isError && (
										<p className="text-xs text-red-500">{socialPublishMutation.error.message}</p>
									)}
								</div>
							)}

							{/* Images section */}
							<div className="space-y-2">
								<h3 className="text-xs font-medium uppercase tracking-wider text-zinc-400">
									Images
								</h3>
								{images.length > 0 && (
									<div className="flex flex-wrap gap-2">
										{images.map((img) => (
											<div key={img.filename} className="group relative shrink-0">
												<img
													src={`/api/studio/images/${img.relative_path}`}
													alt={img.role}
													className="h-16 w-auto rounded border border-zinc-200 object-cover dark:border-zinc-700"
													onError={(e) => {
														(e.target as HTMLImageElement).style.display = "none";
													}}
												/>
												<span className="absolute bottom-0 left-0 right-0 rounded-b bg-black/50 px-0.5 text-center text-[9px] text-white">
													{img.role}
												</span>
											</div>
										))}
									</div>
								)}
								<div className="flex items-center gap-2">
									<select
										value={imageMood}
										onChange={(e) => setImageMood(e.target.value as (typeof MOODS)[number])}
										disabled={batchImageMutation.isPending}
										className="rounded border border-zinc-300 bg-white px-2 py-1.5 text-xs disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-900"
									>
										{MOODS.map((m) => (
											<option key={m} value={m}>
												{m}
											</option>
										))}
									</select>
									<button
										type="button"
										onClick={() => batchImageMutation.mutate(imageMood)}
										disabled={batchImageMutation.isPending}
										className="flex items-center gap-1.5 rounded-lg bg-zinc-800 px-3 py-1.5 text-xs font-medium text-white hover:bg-zinc-700 disabled:opacity-40 dark:bg-zinc-200 dark:text-zinc-900 dark:hover:bg-zinc-300"
									>
										{batchImageMutation.isPending ? (
											<>
												<Loader2 className="h-3 w-3 animate-spin" />
												Generating 3 images...
											</>
										) : (
											<>
												<ImagePlus className="h-3 w-3" />
												Generate All Images
											</>
										)}
									</button>
								</div>
								{batchImageMutation.isError && (
									<p className="text-xs text-red-500">{batchImageMutation.error.message}</p>
								)}
							</div>
						</div>
					</div>

					{/* Chat panel */}
					<div
						className={`${mobileView === "chat" ? "flex" : "hidden md:flex"} min-h-0 flex-1 flex-col overflow-y-auto`}
					>
						<AgentChat
							key={`${slug ?? ""}-${chatPlatform}`}
							content={data.content}
							platform={chatPlatform}
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

	if (platform === "reddit") {
		const lines = content.split("\n");
		const title = lines[0] ?? "";
		const body = lines.slice(2).join("\n").trim() || lines.slice(1).join("\n").trim();
		return (
			<div className="space-y-2">
				<div className="flex items-center gap-2 border-l-4 border-orange-500 pl-3">
					<div className="h-6 w-6 rounded-full bg-orange-100 text-center text-xs font-bold leading-6 text-orange-600 dark:bg-orange-900 dark:text-orange-300">
						r/
					</div>
					<p className="text-sm font-semibold text-zinc-800 dark:text-zinc-200">{title}</p>
				</div>
				<p className="whitespace-pre-wrap text-sm leading-relaxed text-zinc-700 dark:text-zinc-300">
					{body}
				</p>
				<p className="text-xs text-zinc-400">{content.length.toLocaleString()} chars</p>
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
