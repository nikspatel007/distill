import { useChat } from "@ai-sdk/react";
import { TextStreamChatTransport } from "ai";
import type { UIMessage } from "ai";
import { Send } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef } from "react";
import type { ChatMessage } from "../../../shared/schemas.js";

interface AgentChatProps {
	content: string;
	platform: string;
	slug: string;
	chatHistory: ChatMessage[];
	onPlatformContent: (content: string) => void;
	onImageGenerated: (url: string, alt: string) => void;
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

export function AgentChat({
	content,
	platform,
	slug,
	chatHistory,
	onPlatformContent,
	onImageGenerated,
	onHistoryChange,
}: AgentChatProps) {
	const scrollRef = useRef<HTMLDivElement>(null);
	const inputRef = useRef<HTMLTextAreaElement>(null);
	const processedToolCallsRef = useRef<Set<string>>(new Set());

	const initialMessages = useMemo(() => toInitialMessages(chatHistory), [chatHistory]);

	const transport = useMemo(
		() =>
			new TextStreamChatTransport({
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
				if (part.type === "tool-savePlatformContent" || part.type === "dynamic-tool") {
					const toolPart = part as {
						type: string;
						toolCallId: string;
						state: string;
						input?: { content?: string };
						output?: { saved?: boolean; platform?: string };
						toolName?: string;
					};

					// Only process completed tool calls
					if (toolPart.state !== "output-available") continue;

					const partKey = `${msg.id}-${toolPart.toolCallId}`;
					if (processedToolCallsRef.current.has(partKey)) continue;

					if (
						toolPart.type === "tool-savePlatformContent" ||
						(toolPart.type === "dynamic-tool" && toolPart.toolName === "savePlatformContent")
					) {
						processedToolCallsRef.current.add(partKey);
						if (toolPart.input?.content) {
							onPlatformContent(toolPart.input.content);
						}
					}
				}
				if (part.type === "tool-generateImage" || part.type === "dynamic-tool") {
					const toolPart = part as {
						type: string;
						toolCallId: string;
						state: string;
						output?: { url?: string; alt?: string; error?: string };
						toolName?: string;
					};

					if (toolPart.state !== "output-available") continue;

					const partKey = `${msg.id}-${toolPart.toolCallId}`;
					if (processedToolCallsRef.current.has(partKey)) continue;

					if (
						toolPart.type === "tool-generateImage" ||
						(toolPart.type === "dynamic-tool" && toolPart.toolName === "generateImage")
					) {
						if (toolPart.output?.url && !toolPart.output.error) {
							processedToolCallsRef.current.add(partKey);
							onImageGenerated(toolPart.output.url, toolPart.output.alt ?? "");
						}
					}
				}
			}
		}
	}, [messages, onPlatformContent, onImageGenerated]);

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
										return (
											<div
												key={`${msg.id}-text-${pi}`}
												className={`rounded-xl px-3.5 py-2.5 text-sm leading-relaxed ${
													msg.role === "user"
														? "bg-indigo-600 text-white"
														: "bg-zinc-100 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-200"
												}`}
											>
												<p className="whitespace-pre-wrap">{part.text}</p>
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
						className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-30"
					>
						<Send className="h-4 w-4" />
					</button>
				</div>
			</div>
		</div>
	);
}
