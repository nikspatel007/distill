import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "@tanstack/react-router";
import { ArrowLeft, PanelRightClose, PanelRightOpen } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import type { ChatMessage, PlatformContent, ReviewItem } from "../../shared/schemas.js";
import { MarkdownRenderer } from "../components/shared/MarkdownRenderer.js";
import { AgentChat } from "../components/studio/AgentChat.js";
import { PlatformBar } from "../components/studio/PlatformBar.js";

interface StudioItemResponse {
	slug: string;
	title: string;
	type: string;
	content: string;
	frontmatter: Record<string, unknown>;
	review: ReviewItem;
}

export default function StudioDetail() {
	const { slug } = useParams({ strict: false });
	const queryClient = useQueryClient();

	const [chatOpen, setChatOpen] = useState(true);
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

	// Sync state from server on initial load
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

	const savePlatformMutation = useMutation({
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

	const handleChatResponse = useCallback(
		(_response: string, adaptedContent: string, newHistory: ChatMessage[]) => {
			setChatHistory(newHistory);
			saveChatMutation.mutate(newHistory);

			if (adaptedContent) {
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
				savePlatformMutation.mutate({
					platform: selectedPlatform,
					content: adaptedContent,
				});
			}
		},
		[selectedPlatform, saveChatMutation, savePlatformMutation],
	);

	if (isLoading) {
		return <div className="animate-pulse text-zinc-400">Loading...</div>;
	}
	if (error) {
		return <div className="text-red-500">Error: {error.message}</div>;
	}
	if (!data) return null;

	return (
		<div className="-mx-6 -mt-6 flex h-[calc(100vh-3rem)] flex-col">
			{/* Header */}
			<div className="flex items-center justify-between border-b border-zinc-200 px-4 py-3 dark:border-zinc-800">
				<div className="flex items-center gap-3">
					<Link to="/studio" className="text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200">
						<ArrowLeft className="h-5 w-5" />
					</Link>
					<div>
						<h1 className="text-lg font-bold">{data.title}</h1>
						<span
							className={`rounded-full px-2 py-0.5 text-xs font-medium ${
								data.type === "weekly"
									? "bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300"
									: "bg-green-50 text-green-700 dark:bg-green-950 dark:text-green-300"
							}`}
						>
							{data.type}
						</span>
					</div>
				</div>
				<button
					type="button"
					onClick={() => setChatOpen(!chatOpen)}
					className="rounded-lg p-2 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700 dark:hover:bg-zinc-800 dark:hover:text-zinc-200"
				>
					{chatOpen ? (
						<PanelRightClose className="h-5 w-5" />
					) : (
						<PanelRightOpen className="h-5 w-5" />
					)}
				</button>
			</div>

			{/* Main content area */}
			<div className="flex min-h-0 flex-1">
				{/* Editor / content viewer */}
				<div className={`flex-1 overflow-y-auto p-6 ${chatOpen ? "w-1/2" : "w-full"}`}>
					<MarkdownRenderer content={data.content} />
				</div>

				{/* Chat panel */}
				{chatOpen && (
					<div className="w-1/2 min-w-[320px] max-w-[480px]">
						<AgentChat
							content={data.content}
							platform={selectedPlatform}
							chatHistory={chatHistory}
							onResponse={handleChatResponse}
						/>
					</div>
				)}
			</div>

			{/* Platform bar */}
			<PlatformBar
				slug={slug ?? ""}
				selectedPlatform={selectedPlatform}
				onSelectPlatform={setSelectedPlatform}
				platforms={platforms}
			/>
		</div>
	);
}
