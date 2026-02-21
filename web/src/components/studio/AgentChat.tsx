import { useMutation } from "@tanstack/react-query";
import { Send } from "lucide-react";
import { useCallback, useRef, useState } from "react";
import type { ChatMessage } from "../../../shared/schemas.js";

/** Inline type for legacy SSE stream events (schemas removed in AI SDK migration). */
type StudioStreamEvent =
	| { type: "text_delta"; text: string }
	| { type: "done"; response: string; adapted_content: string }
	| { type: "error"; error: string };

interface AgentChatProps {
	content: string;
	platform: string;
	chatHistory: ChatMessage[];
	onResponse: (response: string, adaptedContent: string, newHistory: ChatMessage[]) => void;
}

/**
 * Stream chat via SSE endpoint. Falls back to blocking endpoint on failure.
 */
async function streamChat(
	body: { content: string; platform: string; message: string; history: ChatMessage[] },
	onDelta: (text: string) => void,
): Promise<{ response: string; adapted_content: string }> {
	const res = await fetch("/api/studio/chat/stream", {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(body),
	});

	// If streaming endpoint fails (e.g. 503), fall back to blocking
	if (!res.ok) {
		const fallbackRes = await fetch("/api/studio/chat", {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify(body),
		});
		if (!fallbackRes.ok) {
			const err = await fallbackRes.json().catch(() => ({ error: "Unknown error" }));
			throw new Error(err.error || "Chat failed");
		}
		return fallbackRes.json();
	}

	// Read SSE stream
	const reader = res.body?.getReader();
	if (!reader) {
		throw new Error("No response body");
	}

	const decoder = new TextDecoder();
	let buffer = "";
	let result: { response: string; adapted_content: string } | null = null;

	while (true) {
		const { done, value } = await reader.read();
		if (done) break;

		buffer += decoder.decode(value, { stream: true });

		// Parse SSE lines
		const lines = buffer.split("\n");
		// Keep incomplete last line in buffer
		buffer = lines.pop() ?? "";

		for (const line of lines) {
			if (!line.startsWith("data: ")) continue;
			const json = line.slice(6).trim();
			if (!json) continue;

			try {
				const event = JSON.parse(json) as StudioStreamEvent;

				if (event.type === "text_delta") {
					onDelta(event.text);
				} else if (event.type === "done") {
					result = {
						response: event.response,
						adapted_content: event.adapted_content,
					};
				} else if (event.type === "error") {
					throw new Error(event.error);
				}
			} catch (e) {
				if (e instanceof SyntaxError) continue;
				throw e;
			}
		}
	}

	if (!result) {
		throw new Error("Stream ended without done event");
	}
	return result;
}

export function AgentChat({ content, platform, chatHistory, onResponse }: AgentChatProps) {
	const [input, setInput] = useState("");
	const [error, setError] = useState<string | null>(null);
	const [streamingText, setStreamingText] = useState("");
	const scrollRef = useRef<HTMLDivElement>(null);
	const inputRef = useRef<HTMLTextAreaElement>(null);

	const onDelta = useCallback((text: string) => {
		setStreamingText((prev) => prev + text);
	}, []);

	const chatMutation = useMutation({
		mutationFn: async (message: string) => {
			setStreamingText("");
			return streamChat({ content, platform, message, history: chatHistory }, onDelta);
		},
		onSuccess: (data, message) => {
			setError(null);
			setStreamingText("");
			const now = new Date().toISOString();
			const userMsg: ChatMessage = {
				role: "user",
				content: message,
				timestamp: now,
			};
			const assistantMsg: ChatMessage = {
				role: "assistant",
				content: data.response,
				timestamp: now,
			};
			const newHistory = [...chatHistory, userMsg, assistantMsg];
			onResponse(data.response, data.adapted_content, newHistory);
			setTimeout(() => {
				scrollRef.current?.scrollTo({
					top: scrollRef.current.scrollHeight,
					behavior: "smooth",
				});
			}, 50);
		},
		onError: (err: Error) => {
			setStreamingText("");
			setError(err.message);
		},
	});

	const handleSend = () => {
		const trimmed = input.trim();
		if (!trimmed || chatMutation.isPending) return;
		setInput("");
		chatMutation.mutate(trimmed);
	};

	const handleKeyDown = (e: React.KeyboardEvent) => {
		if (e.key === "Enter" && !e.shiftKey) {
			e.preventDefault();
			handleSend();
		}
	};

	const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
		setInput(e.target.value);
		e.target.style.height = "auto";
		e.target.style.height = `${Math.min(e.target.scrollHeight, 120)}px`;
	};

	return (
		<div ref={scrollRef} className="flex flex-col">
			{/* Messages */}
			{chatHistory.length > 0 && (
				<div className="space-y-3 px-4 pb-3">
					{chatHistory.map((msg, i) => (
						<div
							key={`${msg.timestamp}-${i}`}
							className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
						>
							<div
								className={`max-w-[90%] rounded-xl px-3.5 py-2.5 text-sm leading-relaxed ${
									msg.role === "user"
										? "bg-indigo-600 text-white"
										: "bg-zinc-100 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-200"
								}`}
							>
								<p className="whitespace-pre-wrap">{msg.content}</p>
							</div>
						</div>
					))}
				</div>
			)}

			{/* Streaming response */}
			{chatMutation.isPending && streamingText && (
				<div className="flex justify-start px-4 pb-3">
					<div className="max-w-[90%] rounded-xl bg-zinc-100 px-3.5 py-2.5 text-sm leading-relaxed text-zinc-800 dark:bg-zinc-800 dark:text-zinc-200">
						<p className="whitespace-pre-wrap">{streamingText}</p>
					</div>
				</div>
			)}

			{/* Thinking indicator (no streaming text yet) */}
			{chatMutation.isPending && !streamingText && (
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
					{error}
				</div>
			)}

			{/* Input */}
			<div className="sticky bottom-0 border-t border-zinc-200 bg-white px-4 py-3 dark:border-zinc-800 dark:bg-zinc-950">
				<div className="flex items-end gap-2">
					<textarea
						ref={inputRef}
						value={input}
						onChange={handleInput}
						onKeyDown={handleKeyDown}
						disabled={chatMutation.isPending}
						placeholder={`Write or refine ${platform} content...`}
						rows={1}
						className="flex-1 resize-none rounded-xl border border-zinc-300 bg-white px-3.5 py-2.5 text-sm leading-relaxed placeholder-zinc-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-900 dark:placeholder-zinc-500"
					/>
					<button
						type="button"
						onClick={handleSend}
						disabled={chatMutation.isPending || !input.trim()}
						className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-30"
					>
						<Send className="h-4 w-4" />
					</button>
				</div>
			</div>
		</div>
	);
}
