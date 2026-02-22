import { useChat } from "@ai-sdk/react";
import { DefaultChatTransport } from "ai";
import type { UIMessage } from "ai";
import { Send } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef } from "react";
import type { ChatMessage } from "../../../shared/schemas.js";
import { MarkdownRenderer } from "../shared/MarkdownRenderer.js";

interface AgentChatProps {
	content: string;
	platform: string;
	slug: string;
	chatHistory: ChatMessage[];
	onPlatformContent: (content: string) => void;
	onImageGenerated: (url: string, alt: string) => void;
	onSourceUpdated: () => void;
	onHistoryChange: (messages: ChatMessage[]) => void;
}

/** Convert our store ChatMessage[] to AI SDK UIMessage[] for initialMessages. */
function toInitialMessages(history: ChatMessage[]): UIMessage[] {
	return history.map((msg, i) => ({
		id: `hist-${i}`,
		role: msg.role as "user" | "assistant",
		parts: [{ type: "text" as const, text: msg.content }],
	}));
}

/** Convert AI SDK UIMessage[] back to our store ChatMessage[] for persistence. */
function toStoreChatMessages(messages: UIMessage[]): ChatMessage[] {
	const now = new Date().toISOString();
	return messages
		.filter((m) => m.role === "user" || m.role === "assistant")
		.map((m) => {
			// Extract text from parts
			const textParts = m.parts
				.filter((p): p is { type: "text"; text: string } => p.type === "text")
				.map((p) => p.text);
			return {
				role: m.role as "user" | "assistant",
				content: textParts.join("") || "",
				timestamp: now,
			};
		});
}

/** Labels and colors for tool result chips. */
const TOOL_CHIPS: Record<string, { label: string; color: string }> = {
	runPipeline: { label: "Pipeline completed", color: "indigo" },
	runJournal: { label: "Journal generated", color: "indigo" },
	runBlog: { label: "Blog generated", color: "indigo" },
	runIntake: { label: "Intake completed", color: "indigo" },
	addSeed: { label: "Seed idea saved", color: "amber" },
	addNote: { label: "Editorial note saved", color: "amber" },
	fetchUrl: { label: "URL fetched", color: "sky" },
	saveToIntake: { label: "Saved to intake", color: "sky" },
	publishContent: { label: "Content published", color: "green" },
	listPostizIntegrations: { label: "Integrations loaded", color: "zinc" },
	listPostizPosts: { label: "Posts loaded", color: "zinc" },
	listContent: { label: "Content listed", color: "zinc" },
	getContent: { label: "Content loaded", color: "zinc" },
	createContent: { label: "Content created", color: "green" },
	updateContentStatus: { label: "Status updated", color: "blue" },
	deleteContent: { label: "Content deleted", color: "red" },
};

const CHIP_COLORS: Record<string, string> = {
	indigo:
		"bg-indigo-50 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300 [&>span]:text-indigo-500",
	amber: "bg-amber-50 text-amber-700 dark:bg-amber-950 dark:text-amber-300 [&>span]:text-amber-500",
	sky: "bg-sky-50 text-sky-700 dark:bg-sky-950 dark:text-sky-300 [&>span]:text-sky-500",
	green: "bg-green-50 text-green-700 dark:bg-green-950 dark:text-green-300 [&>span]:text-green-500",
	blue: "bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300 [&>span]:text-blue-500",
	zinc: "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400 [&>span]:text-zinc-400",
	red: "bg-red-50 text-red-700 dark:bg-red-950 dark:text-red-300 [&>span]:text-red-500",
};

export function AgentChat({
	content,
	platform,
	slug,
	chatHistory,
	onPlatformContent,
	onImageGenerated,
	onSourceUpdated,
	onHistoryChange,
}: AgentChatProps) {
	const scrollRef = useRef<HTMLDivElement>(null);
	const inputRef = useRef<HTMLTextAreaElement>(null);
	const processedToolCallsRef = useRef<Set<string>>(new Set());

	const initialMessages = useMemo(() => toInitialMessages(chatHistory), [chatHistory]);

	const transport = useMemo(
		() =>
			new DefaultChatTransport({
				api: "/api/studio/chat",
				body: { content, platform, slug },
			}),
		[content, platform, slug],
	);

	const { messages, sendMessage, status, error, setMessages } = useChat({
		transport,
		messages: initialMessages,
		onFinish: useCallback(
			({ messages: finishedMessages }: { messages: UIMessage[] }) => {
				onHistoryChange(toStoreChatMessages(finishedMessages));
			},
			[onHistoryChange],
		),
	});

	// Scan messages for tool results to trigger callbacks
	useEffect(() => {
		for (const msg of messages) {
			if (msg.role !== "assistant") continue;
			for (const part of msg.parts) {
				const toolPart = part as {
					type: string;
					toolCallId?: string;
					state?: string;
					toolName?: string;
					input?: { content?: string };
					output?: Record<string, unknown>;
				};

				// Only handle tool parts with completed state
				if (!toolPart.toolCallId || toolPart.state !== "output-available") continue;

				const partKey = `${msg.id}-${toolPart.toolCallId}`;
				if (processedToolCallsRef.current.has(partKey)) continue;

				const isToolType = (name: string) =>
					toolPart.type === `tool-${name}` ||
					(toolPart.type === "dynamic-tool" && toolPart.toolName === name);

				if (isToolType("savePlatformContent") && toolPart.input?.content) {
					processedToolCallsRef.current.add(partKey);
					onPlatformContent(toolPart.input.content);
					// biome-ignore lint/complexity/useLiteralKeys: tsc noPropertyAccessFromIndexSignature
				} else if (isToolType("updateSourceContent") && toolPart.output?.["saved"]) {
					processedToolCallsRef.current.add(partKey);
					onSourceUpdated();
				} else if (isToolType("generateImage")) {
					const output = toolPart.output as
						| { url?: string; alt?: string; error?: string }
						| undefined;
					if (output?.url && !output.error) {
						processedToolCallsRef.current.add(partKey);
						onImageGenerated(output.url, output.alt ?? "");
					}
				}
			}
		}
	}, [messages, onPlatformContent, onImageGenerated, onSourceUpdated]);

	// Sync external chatHistory changes (e.g., platform switch reloads)
	useEffect(() => {
		if (chatHistory.length > 0 && messages.length === 0) {
			setMessages(toInitialMessages(chatHistory));
		}
	}, [chatHistory, messages.length, setMessages]);

	// Auto-scroll to bottom on new messages
	const prevMsgCountRef = useRef(messages.length);
	useEffect(() => {
		if (messages.length !== prevMsgCountRef.current) {
			prevMsgCountRef.current = messages.length;
			setTimeout(() => {
				scrollRef.current?.scrollTo({
					top: scrollRef.current.scrollHeight,
					behavior: "smooth",
				});
			}, 50);
		}
	}, [messages.length]);

	const handleSend = useCallback(() => {
		const textarea = inputRef.current;
		if (!textarea) return;
		const trimmed = textarea.value.trim();
		if (!trimmed || status !== "ready") return;
		textarea.value = "";
		textarea.style.height = "auto";
		sendMessage({ text: trimmed });
	}, [sendMessage, status]);

	const handleKeyDown = useCallback(
		(e: React.KeyboardEvent) => {
			if (e.key === "Enter" && !e.shiftKey) {
				e.preventDefault();
				handleSend();
			}
		},
		[handleSend],
	);

	const handleInput = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
		e.target.style.height = "auto";
		e.target.style.height = `${Math.min(e.target.scrollHeight, 120)}px`;
	}, []);

	const isBusy = status === "submitted" || status === "streaming";

	return (
		<div ref={scrollRef} className="flex flex-col">
			{/* Messages */}
			{messages.length > 0 && (
				<div className="space-y-3 px-4 pb-3">
					{messages.map((msg) => (
						<div
							key={msg.id}
							className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
						>
							<div className="max-w-[90%] space-y-2">
								{msg.parts.map((part, pi) => {
									if (part.type === "text" && part.text) {
										return msg.role === "user" ? (
											<div
												key={`${msg.id}-text-${pi}`}
												className="rounded-xl bg-indigo-600 px-3.5 py-2.5 text-sm leading-relaxed text-white"
											>
												<p className="whitespace-pre-wrap">{part.text}</p>
											</div>
										) : (
											<div
												key={`${msg.id}-text-${pi}`}
												className="chat-markdown rounded-xl bg-zinc-100 px-3.5 py-2.5 text-sm leading-relaxed text-zinc-800 dark:bg-zinc-800 dark:text-zinc-200"
											>
												<MarkdownRenderer
													content={part.text}
													className="prose prose-sm prose-zinc dark:prose-invert max-w-none"
												/>
											</div>
										);
									}

									// Tool: savePlatformContent result
									if (
										part.type === "tool-savePlatformContent" ||
										(part.type === "dynamic-tool" &&
											"toolName" in part &&
											part.toolName === "savePlatformContent")
									) {
										const toolPart = part as { state: string };
										if (toolPart.state === "output-available") {
											return (
												<div
													key={`${msg.id}-tool-${pi}`}
													className="flex items-center gap-1.5 rounded-lg bg-green-50 px-3 py-1.5 text-xs font-medium text-green-700 dark:bg-green-950 dark:text-green-300"
												>
													<span className="text-green-500">&#10003;</span>
													Content saved to {platform}
												</div>
											);
										}
										return null;
									}

									// Tool: updateSourceContent result
									if (
										part.type === "tool-updateSourceContent" ||
										(part.type === "dynamic-tool" &&
											"toolName" in part &&
											part.toolName === "updateSourceContent")
									) {
										const toolPart = part as { state: string };
										if (toolPart.state === "output-available") {
											return (
												<div
													key={`${msg.id}-source-${pi}`}
													className="flex items-center gap-1.5 rounded-lg bg-blue-50 px-3 py-1.5 text-xs font-medium text-blue-700 dark:bg-blue-950 dark:text-blue-300"
												>
													<span className="text-blue-500">&#10003;</span>
													Source post updated
												</div>
											);
										}
										return null;
									}

									// Tool: generateImage result
									if (
										part.type === "tool-generateImage" ||
										(part.type === "dynamic-tool" &&
											"toolName" in part &&
											part.toolName === "generateImage")
									) {
										const toolPart = part as {
											state: string;
											output?: { url?: string; alt?: string; error?: string };
										};
										if (toolPart.state === "output-available" && toolPart.output?.url) {
											return (
												<div
													key={`${msg.id}-img-${pi}`}
													className="overflow-hidden rounded-lg border border-zinc-200 dark:border-zinc-700"
												>
													<img
														src={toolPart.output.url}
														alt={toolPart.output.alt ?? "Generated image"}
														className="max-h-64 w-full object-cover"
													/>
												</div>
											);
										}
										if (toolPart.state === "output-available" && toolPart.output?.error) {
											return (
												<div
													key={`${msg.id}-imgerr-${pi}`}
													className="rounded-lg bg-red-50 px-3 py-1.5 text-xs text-red-600 dark:bg-red-950 dark:text-red-400"
												>
													Image generation failed: {toolPart.output.error}
												</div>
											);
										}
										return null;
									}

									// Generic tool chips for pipeline/research/publish tools
									{
										const toolPart = part as {
											type: string;
											state?: string;
											toolName?: string;
											output?: Record<string, unknown>;
										};
										if (toolPart.state === "output-available") {
											// Determine tool name from part type
											let toolName = "";
											if (toolPart.type.startsWith("tool-")) {
												toolName = toolPart.type.slice(5);
											} else if (toolPart.type === "dynamic-tool" && toolPart.toolName) {
												toolName = toolPart.toolName;
											}
											const chip = TOOL_CHIPS[toolName];
											if (chip) {
												// biome-ignore lint/complexity/useLiteralKeys: tsc noPropertyAccessFromIndexSignature
												const hasError = toolPart.output?.["error"];
												if (hasError) {
													return (
														<div
															key={`${msg.id}-tool-${pi}`}
															className="rounded-lg bg-red-50 px-3 py-1.5 text-xs text-red-600 dark:bg-red-950 dark:text-red-400"
														>
															{/* biome-ignore lint/complexity/useLiteralKeys: tsc noPropertyAccessFromIndexSignature */}
															{chip.label} failed: {String(toolPart.output?.["error"])}
														</div>
													);
												}
												const colorCls =
													CHIP_COLORS[chip.color] ??
													"bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400 [&>span]:text-zinc-400";
												return (
													<div
														key={`${msg.id}-tool-${pi}`}
														className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium ${colorCls}`}
													>
														<span>&#10003;</span>
														{chip.label}
													</div>
												);
											}
										}
									}

									return null;
								})}
							</div>
						</div>
					))}
				</div>
			)}

			{/* Thinking indicator */}
			{status === "submitted" && (
				<div className="flex justify-start px-4 pb-3">
					<div className="flex items-center gap-2 rounded-xl bg-zinc-100 px-3.5 py-2.5 text-sm text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400">
						<span className="inline-flex gap-1">
							<span className="animate-bounce [animation-delay:0ms]">.</span>
							<span className="animate-bounce [animation-delay:150ms]">.</span>
							<span className="animate-bounce [animation-delay:300ms]">.</span>
						</span>
						Claude is thinking
					</div>
				</div>
			)}

			{error && (
				<div className="mx-4 mb-3 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-600 dark:bg-red-950 dark:text-red-400">
					{error.message}
				</div>
			)}

			{/* Input */}
			<div className="sticky bottom-0 border-t border-zinc-200 bg-white px-4 py-3 dark:border-zinc-800 dark:bg-zinc-950">
				<div className="flex items-end gap-2">
					<textarea
						ref={inputRef}
						onChange={handleInput}
						onKeyDown={handleKeyDown}
						disabled={isBusy}
						placeholder={`Write or refine ${platform} content...`}
						rows={1}
						className="flex-1 resize-none rounded-xl border border-zinc-300 bg-white px-3.5 py-2.5 text-sm leading-relaxed placeholder-zinc-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-900 dark:placeholder-zinc-500"
					/>
					<button
						type="button"
						onClick={handleSend}
						disabled={isBusy}
						className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-30"
					>
						<Send className="h-4 w-4" />
					</button>
				</div>
			</div>
		</div>
	);
}
