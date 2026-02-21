/**
 * Anthropic model factory for Studio chat.
 *
 * Uses @ai-sdk/anthropic for direct Anthropic API calls.
 * Reads ANTHROPIC_API_KEY from environment automatically.
 */
import { createAnthropic } from "@ai-sdk/anthropic";
import type { LanguageModelV3 } from "@ai-sdk/provider";

const DEFAULT_MODEL = "claude-sonnet-4-5-20250929";

/**
 * Check whether the Anthropic API key is available.
 */
export function isAgentConfigured(): boolean {
	// biome-ignore lint/complexity/useLiteralKeys: tsc noPropertyAccessFromIndexSignature requires bracket notation
	return !!process.env["ANTHROPIC_API_KEY"];
}

/**
 * Get the Anthropic language model for streamText/generateText.
 */
export function getModel(modelId?: string): LanguageModelV3 {
	const anthropic = createAnthropic();
	return anthropic(modelId ?? DEFAULT_MODEL);
}
