import { useMutation } from "@tanstack/react-query";
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
			return res.json() as Promise<{ response: string; adapted_content: string }>;
		},
		onSuccess: (data, message) => {
			setError(null);
			const now = new Date().toISOString();
			const userMsg: ChatMessage = { role: "user", content: message, timestamp: now };
			const assistantMsg: ChatMessage = {
				role: "assistant",
				content: data.response,
				timestamp: now,
			};
			const newHistory = [...chatHistory, userMsg, assistantMsg];
			onResponse(data.response, data.adapted_content, newHistory);
			setTimeout(() => {
				scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
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

	return (
		<div className="flex h-full flex-col border-l border-zinc-200 dark:border-zinc-800">
			<div className="border-b border-zinc-200 px-4 py-3 dark:border-zinc-800">
				<h3 className="text-sm font-semibold">
					Adapting for <span className="capitalize">{platform}</span>
				</h3>
			</div>

			<div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto p-4">
				{chatHistory.length === 0 && !chatMutation.isPending && (
					<div className="flex h-full items-center justify-center">
						<p className="text-center text-sm text-zinc-400">
							Ask Claude to adapt your content for{" "}
							<span className="font-medium capitalize">{platform}</span>.
						</p>
					</div>
				)}

				{chatHistory.map((msg, i) => (
					<div
						key={`${msg.timestamp}-${i}`}
						className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
					>
						<div
							className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${
								msg.role === "user"
									? "bg-indigo-600 text-white"
									: "bg-zinc-100 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-200"
							}`}
						>
							<p className="whitespace-pre-wrap">{msg.content}</p>
						</div>
					</div>
				))}

				{chatMutation.isPending && (
					<div className="flex justify-start">
						<div className="rounded-lg bg-zinc-100 px-3 py-2 text-sm text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400">
							Claude is thinking...
						</div>
					</div>
				)}
			</div>

			{error && (
				<div className="border-t border-red-200 bg-red-50 px-4 py-2 text-xs text-red-600 dark:border-red-900 dark:bg-red-950 dark:text-red-400">
					{error}
				</div>
			)}

			<div className="border-t border-zinc-200 p-3 dark:border-zinc-800">
				<div className="flex gap-2">
					<input
						type="text"
						value={input}
						onChange={(e) => setInput(e.target.value)}
						onKeyDown={handleKeyDown}
						disabled={chatMutation.isPending}
						placeholder={`Ask Claude about ${platform} adaptation...`}
						className="flex-1 rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm placeholder-zinc-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-900 dark:placeholder-zinc-500"
					/>
					<button
						type="button"
						onClick={handleSend}
						disabled={chatMutation.isPending || !input.trim()}
						className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
					>
						Send
					</button>
				</div>
			</div>
		</div>
	);
}
