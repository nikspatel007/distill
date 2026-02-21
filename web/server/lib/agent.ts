/**
 * Agent SDK wrapper for Studio chat.
 *
 * Uses @anthropic-ai/claude-agent-sdk to call Claude with proper system prompts
 * and no tools (text generation only). Supports both blocking and streaming modes.
 */
import { type Options, type Query, query } from "@anthropic-ai/claude-agent-sdk";

/**
 * Check whether the Agent SDK can be used.
 * The SDK reads ANTHROPIC_API_KEY from the environment automatically.
 */
export function isAgentConfigured(): boolean {
	// biome-ignore lint/complexity/useLiteralKeys: tsc noPropertyAccessFromIndexSignature requires bracket notation
	return !!process.env["ANTHROPIC_API_KEY"];
}

/**
 * Build a clean env for the Agent SDK subprocess.
 * Unsets CLAUDECODE to allow the SDK to spawn Claude Code
 * even when the server itself runs inside a Claude Code session.
 */
function cleanEnv(): Record<string, string | undefined> {
	const { CLAUDECODE: _, ...env } = process.env;
	return env;
}

/** Default options shared by blocking and streaming calls. */
function baseOptions(systemPrompt: string): Options {
	return {
		systemPrompt: systemPrompt,
		maxTurns: 1,
		allowedTools: [],
		permissionMode: "bypassPermissions",
		allowDangerouslySkipPermissions: true,
		env: cleanEnv(),
	};
}

/**
 * Call Claude via the Agent SDK (blocking — collects full response).
 * Returns the concatenated text from all AssistantMessage TextBlocks.
 */
export async function callAgent(prompt: string, systemPrompt: string): Promise<string> {
	const q = query({
		prompt,
		options: baseOptions(systemPrompt),
	});

	const textParts: string[] = [];
	for await (const message of q) {
		if (message.type === "assistant") {
			const content = (
				message as { message?: { content?: Array<{ type: string; text?: string }> } }
			).message?.content;
			if (content) {
				for (const block of content) {
					if (block.type === "text" && block.text) {
						textParts.push(block.text);
					}
				}
			}
		}
	}

	return textParts.join("").trim();
}

/**
 * Call Claude via the Agent SDK with streaming (partial messages).
 * Returns a Query async generator that yields SDKMessage events.
 * The caller should iterate and look for stream_event messages.
 */
export function callAgentStreaming(prompt: string, systemPrompt: string): Query {
	return query({
		prompt,
		options: {
			...baseOptions(systemPrompt),
			includePartialMessages: true,
		},
	});
}
