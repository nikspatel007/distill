import { useMutation } from "@tanstack/react-query";
import { Send } from "lucide-react";
import { useRef, useState } from "react";
import type { ChatMessage } from "../../../shared/schemas.js";

interface AgentChatProps {
	content: string;
	platform: string;
	chatHistory: ChatMessage[];
	onResponse: (response: string, adaptedContent: string, newHistory: ChatMessage[]) => void;
}

export function AgentChat({ content, platform, chatHistory, onResponse }: AgentChatProps) {
	const [input, setInput] = useState("");
	const [error, setError] = useState<string | null>(null);
	const scrollRef = useRef<HTMLDivElement>(null);
	const inputRef = useRef<HTMLTextAreaElement>(null);

	const chatMutation = useMutation({
		mutationFn: async (message: string) => {
			const res = await fetch("/api/studio/chat", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					content,
					platform,
					message,
					history: chatHistory,
				}),
			});
			if (!res.ok) {
				const err = await res.json().catch(() => ({ error: "Unknown error" }));
				throw new Error(err.error || "Chat failed");
			}
			return res.json() as Promise<{
				response: string;
				adapted_content: string;
			}>;
		},
		onSuccess: (data, message) => {
			setError(null);
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

			{chatMutation.isPending && (
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
						placeholder={`Refine ${platform} content...`}
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
