# Vercel AI SDK Migration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace Agent SDK (CLI subprocess) with Vercel AI SDK for Studio chat, add tool-based image generation via google-genai, and make chat feel like a natural conversation with proper message threading and streaming.

**Architecture:** Single `streamText()` endpoint with `@ai-sdk/anthropic` replaces both blocking and streaming chat endpoints. Claude gets two tools: `savePlatformContent` (writes adapted content to the content store) and `generateImage` (calls google-genai). Frontend uses `useChat()` hook from `@ai-sdk/react` which handles message state, streaming, and tool results out of the box.

**Tech Stack:** `ai` (Vercel AI SDK core), `@ai-sdk/anthropic` (Anthropic provider), `@ai-sdk/react` (React hooks), `@google/genai` (Google GenAI for images), Hono, Bun, React, TanStack Query

---

### Task 1: Swap Dependencies

**Files:**
- Modify: `web/package.json`

**Step 1: Remove old SDK, add new packages**

```bash
cd /Users/nikpatel/Documents/GitHub/distill/web
bun remove @anthropic-ai/claude-agent-sdk
bun add ai @ai-sdk/anthropic @ai-sdk/react @google/genai
```

**Step 2: Verify install**

```bash
cd /Users/nikpatel/Documents/GitHub/distill/web && ls node_modules/ai node_modules/@ai-sdk/anthropic node_modules/@ai-sdk/react node_modules/@google/genai
```

Expected: All four directories exist.

**Step 3: Commit**

```bash
cd /Users/nikpatel/Documents/GitHub/distill
git add web/package.json web/bun.lock
git commit -m "chore: swap agent-sdk for ai, @ai-sdk/anthropic, @ai-sdk/react, @google/genai"
```

---

### Task 2: Rewrite `agent.ts` — Anthropic Model Factory

**Files:**
- Modify: `web/server/lib/agent.ts`
- Test: `web/server/__tests__/agent.test.ts` (create)

**Step 1: Write the test**

Create `web/server/__tests__/agent.test.ts`:

```typescript
import { describe, expect, test } from "bun:test";
import { getModel, isAgentConfigured } from "../lib/agent.js";

describe("isAgentConfigured", () => {
	test("returns false when no API key", () => {
		const orig = process.env["ANTHROPIC_API_KEY"];
		delete process.env["ANTHROPIC_API_KEY"];
		expect(isAgentConfigured()).toBe(false);
		if (orig) process.env["ANTHROPIC_API_KEY"] = orig;
	});

	test("returns true when API key is set", () => {
		const orig = process.env["ANTHROPIC_API_KEY"];
		process.env["ANTHROPIC_API_KEY"] = "sk-test";
		expect(isAgentConfigured()).toBe(true);
		if (orig) process.env["ANTHROPIC_API_KEY"] = orig;
		else delete process.env["ANTHROPIC_API_KEY"];
	});
});

describe("getModel", () => {
	test("returns a model object", () => {
		const model = getModel();
		expect(model).toBeDefined();
		expect(model.modelId).toBe("claude-sonnet-4-5-20250929");
	});
});
```

**Step 2: Run test to verify it fails**

```bash
cd /Users/nikpatel/Documents/GitHub/distill/web && bun test server/__tests__/agent.test.ts
```

Expected: FAIL — `getModel` doesn't exist yet.

**Step 3: Rewrite `agent.ts`**

Replace the entire contents of `web/server/lib/agent.ts` with:

```typescript
/**
 * Anthropic model factory for Studio chat.
 *
 * Uses @ai-sdk/anthropic for direct Anthropic API calls.
 * Reads ANTHROPIC_API_KEY from environment automatically.
 */
import { createAnthropic } from "@ai-sdk/anthropic";
import type { LanguageModelV1 } from "ai";

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
export function getModel(modelId?: string): LanguageModelV1 {
	const anthropic = createAnthropic();
	return anthropic(modelId ?? DEFAULT_MODEL);
}
```

**Step 4: Run test to verify it passes**

```bash
cd /Users/nikpatel/Documents/GitHub/distill/web && bun test server/__tests__/agent.test.ts
```

Expected: PASS

**Step 5: Commit**

```bash
cd /Users/nikpatel/Documents/GitHub/distill
git add web/server/lib/agent.ts web/server/__tests__/agent.test.ts
git commit -m "feat: rewrite agent.ts with @ai-sdk/anthropic model factory"
```

---

### Task 3: Create `images.ts` — Google GenAI Image Wrapper

**Files:**
- Create: `web/server/lib/images.ts`
- Test: `web/server/__tests__/images.test.ts` (create)

This mirrors the Python `src/shared/images.py` — same mood-based style prefixes, same graceful fallback.

**Step 1: Write the test**

Create `web/server/__tests__/images.test.ts`:

```typescript
import { afterEach, beforeEach, describe, expect, mock, test } from "bun:test";
import { existsSync, mkdirSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

// We'll mock the @google/genai module
const mockGenerateContent = mock(() =>
	Promise.resolve({
		candidates: [
			{
				content: {
					parts: [
						{
							inlineData: {
								mimeType: "image/png",
								data: "iVBORw0KGgo=", // minimal base64 PNG
							},
						},
					],
				},
			},
		],
	}),
);

mock.module("@google/genai", () => ({
	GoogleGenAI: class {
		models = {
			generateContent: mockGenerateContent,
		};
	},
}));

// Import AFTER mocking
const { isImageConfigured, generateImage, STYLE_PREFIXES } = await import("../lib/images.js");

let tempDir: string;

beforeEach(() => {
	tempDir = mkdtempSync(join(tmpdir(), "images-test-"));
});

afterEach(() => {
	rmSync(tempDir, { recursive: true, force: true });
});

describe("isImageConfigured", () => {
	test("returns false when no API key", () => {
		const orig = process.env["GOOGLE_AI_API_KEY"];
		delete process.env["GOOGLE_AI_API_KEY"];
		expect(isImageConfigured()).toBe(false);
		if (orig) process.env["GOOGLE_AI_API_KEY"] = orig;
	});

	test("returns true when API key is set", () => {
		const orig = process.env["GOOGLE_AI_API_KEY"];
		process.env["GOOGLE_AI_API_KEY"] = "test-key";
		expect(isImageConfigured()).toBe(true);
		if (orig) process.env["GOOGLE_AI_API_KEY"] = orig;
		else delete process.env["GOOGLE_AI_API_KEY"];
	});
});

describe("STYLE_PREFIXES", () => {
	test("has all 8 moods", () => {
		const expected = [
			"reflective",
			"energetic",
			"cautionary",
			"triumphant",
			"intimate",
			"technical",
			"playful",
			"somber",
		];
		for (const mood of expected) {
			expect(STYLE_PREFIXES[mood]).toBeDefined();
		}
	});
});

describe("generateImage", () => {
	test("returns null when not configured", async () => {
		const orig = process.env["GOOGLE_AI_API_KEY"];
		delete process.env["GOOGLE_AI_API_KEY"];
		const result = await generateImage("test prompt", { outputDir: tempDir });
		expect(result).toBeNull();
		if (orig) process.env["GOOGLE_AI_API_KEY"] = orig;
	});

	test("generates image and returns metadata", async () => {
		const orig = process.env["GOOGLE_AI_API_KEY"];
		process.env["GOOGLE_AI_API_KEY"] = "test-key";

		const result = await generateImage("A sunset over the ocean", {
			outputDir: tempDir,
			mood: "reflective",
		});

		expect(result).not.toBeNull();
		expect(result?.filename).toMatch(/\.png$/);
		expect(result?.relativePath).toBeDefined();
		expect(mockGenerateContent).toHaveBeenCalled();

		if (orig) process.env["GOOGLE_AI_API_KEY"] = orig;
		else delete process.env["GOOGLE_AI_API_KEY"];
	});
});
```

**Step 2: Run test to verify it fails**

```bash
cd /Users/nikpatel/Documents/GitHub/distill/web && bun test server/__tests__/images.test.ts
```

Expected: FAIL — `images.js` doesn't exist.

**Step 3: Write the implementation**

Create `web/server/lib/images.ts`:

```typescript
/**
 * Image generation via Google GenAI (Nano Banana Pro / Gemini).
 *
 * Mirrors src/shared/images.py — same mood-based style prefixes,
 * same graceful fallback when not configured.
 */
import { writeFileSync } from "node:fs";
import { join } from "node:path";
import { mkdirSync } from "node:fs";

const DEFAULT_MODEL = "gemini-2.0-flash-preview-image-generation";

/** Mood-indexed style prefixes — identical to Python ImageGenerator. */
export const STYLE_PREFIXES: Record<string, string> = {
	reflective:
		"Contemplative editorial photograph. Diffused overcast light, cool blue-grey palette with desaturated tones. 50mm lens at f/4, moderate depth of field. Symmetrical composition with deliberate negative space. Still, quiet atmosphere. No text, no logos, no UI elements. -- ",
	energetic:
		"Dynamic editorial photograph. Warm golden-hour directional light casting long shadows. 35mm lens at f/2.8, shallow depth of field. Diagonal composition with strong leading lines and a sense of forward motion. Amber and warm-white palette. No text, no logos, no UI elements. -- ",
	cautionary:
		"Tense editorial photograph. Hard directional lighting from a single source, deep shadows with teal-and-orange color contrast. 85mm lens at f/2, tight crop with the subject off-center. Unsettled atmosphere. No text, no logos, no UI elements. -- ",
	triumphant:
		"Bold editorial photograph. Bright high-key lighting, vivid saturated colors. 24mm wide-angle lens at f/8 for deep focus. Expansive composition with a sense of scale and openness. The scene feels earned and resolved. No text, no logos, no UI elements. -- ",
	intimate:
		"Quiet editorial photograph. Soft window light from camera-left, warm muted earth tones with cream and amber highlights. 85mm lens at f/1.8, very shallow depth of field isolating the subject. Close framing, personal scale. No text, no logos, no UI elements. -- ",
	technical:
		"Precise editorial photograph. Clean even studio lighting, cool neutral palette with high clarity. 100mm macro lens or overhead bird's-eye view. Geometric composition with ordered elements. Clinical but elegant. No text, no logos, no UI elements. -- ",
	playful:
		"Whimsical editorial photograph. Bright diffused daylight, slightly warm with pastel accent colors. 35mm lens at f/4, moderate depth. Off-kilter composition with an element of surprise or visual humor. Light and approachable atmosphere. No text, no logos, no UI elements. -- ",
	somber:
		"Subdued editorial photograph. Low-key lighting with chiaroscuro contrast, desaturated palette leaning toward cool greys and muted blues. 135mm telephoto compression, f/2.8. Isolated subject with heavy negative space. Bleach-bypass tonal quality. No text, no logos, no UI elements. -- ",
};

const DEFAULT_STYLE = STYLE_PREFIXES["reflective"] ?? "";

export interface ImageResult {
	filename: string;
	relativePath: string;
	prompt: string;
	mood: string;
}

/**
 * Check whether image generation is available.
 */
export function isImageConfigured(): boolean {
	// biome-ignore lint/complexity/useLiteralKeys: tsc noPropertyAccessFromIndexSignature
	return !!process.env["GOOGLE_AI_API_KEY"];
}

/**
 * Generate an image from a text prompt and save to disk.
 *
 * Returns metadata on success, null if not configured or on error.
 */
export async function generateImage(
	prompt: string,
	options: {
		outputDir: string;
		mood?: string;
		slug?: string;
		aspectRatio?: string;
	},
): Promise<ImageResult | null> {
	if (!isImageConfigured()) {
		return null;
	}

	const { outputDir, mood = "reflective", slug = "image", aspectRatio = "16:9" } = options;
	const style = STYLE_PREFIXES[mood] ?? DEFAULT_STYLE;
	const fullPrompt = style + prompt;

	try {
		// Dynamic import to avoid hard dependency
		const { GoogleGenAI } = await import("@google/genai");
		// biome-ignore lint/complexity/useLiteralKeys: tsc noPropertyAccessFromIndexSignature
		const ai = new GoogleGenAI({ apiKey: process.env["GOOGLE_AI_API_KEY"] ?? "" });

		const response = await ai.models.generateContent({
			model: DEFAULT_MODEL,
			contents: fullPrompt,
			config: {
				responseModalities: ["TEXT", "IMAGE"],
			},
		});

		// Extract image data from response
		const parts = response.candidates?.[0]?.content?.parts ?? [];
		for (const part of parts) {
			if (part.inlineData?.data) {
				const timestamp = Date.now();
				const filename = `${slug}-${timestamp}.png`;
				const imagesDir = join(outputDir, "studio", "images");
				mkdirSync(imagesDir, { recursive: true });
				const filePath = join(imagesDir, filename);
				const buffer = Buffer.from(part.inlineData.data, "base64");
				writeFileSync(filePath, buffer);

				return {
					filename,
					relativePath: `studio/images/${filename}`,
					prompt,
					mood,
				};
			}
		}

		return null;
	} catch (err) {
		console.error("Image generation failed:", err instanceof Error ? err.message : err);
		return null;
	}
}
```

**Step 4: Run test to verify it passes**

```bash
cd /Users/nikpatel/Documents/GitHub/distill/web && bun test server/__tests__/images.test.ts
```

Expected: PASS

**Step 5: Commit**

```bash
cd /Users/nikpatel/Documents/GitHub/distill
git add web/server/lib/images.ts web/server/__tests__/images.test.ts
git commit -m "feat: add google-genai image generation wrapper (images.ts)"
```

---

### Task 4: Rewrite Studio Chat Endpoint

**Files:**
- Modify: `web/server/routes/studio.ts:569-751` (chat section)
- Modify: `web/shared/schemas.ts` (remove `StudioStreamEventSchema`, update chat request schema)

This is the core change: replace both `/api/studio/chat` and `/api/studio/chat/stream` with a single `streamText()` endpoint that returns an AI SDK data stream.

**Step 1: Update schemas**

In `web/shared/schemas.ts`, find and remove the `StudioStreamEventSchema` and its type export. Also update `StudioChatRequestSchema` — the AI SDK sends `messages` instead of `message` + `history`.

Find the `StudioStreamEventSchema` block and remove it entirely. It should look like:

```typescript
export const StudioStreamEventSchema = z.discriminatedUnion("type", [
	z.object({ type: z.literal("text_delta"), text: z.string() }),
	z.object({ type: z.literal("done"), response: z.string(), adapted_content: z.string() }),
	z.object({ type: z.literal("error"), error: z.string() }),
]);
export type StudioStreamEvent = z.infer<typeof StudioStreamEventSchema>;
```

Remove those lines.

Then find `StudioChatRequestSchema` and leave it as-is for now (we'll bypass zod validation for the AI SDK endpoint since the SDK handles its own message format). If you can't find it in schemas.ts, check the imports in studio.ts.

**Step 2: Rewrite the chat section of `studio.ts`**

In `web/server/routes/studio.ts`, replace everything from the chat section comment (around line 569) down to (but not including) the images endpoint.

Remove these lines:
- The `buildChatPrompt()` function
- The `parseChatResponse()` function
- `POST /api/studio/chat` (blocking endpoint)
- `POST /api/studio/chat/stream` (streaming endpoint)

Replace with:

```typescript
// ---------------------------------------------------------------------------
// POST /api/studio/chat — AI SDK streaming chat with tools
// ---------------------------------------------------------------------------
import { streamText, tool } from "ai";
import { getModel, isAgentConfigured } from "../lib/agent.js";
import { generateImage, isImageConfigured } from "../lib/images.js";

const PLATFORM_PROMPTS: Record<string, string> = {
	x: `You are helping craft content for X/Twitter. Create a thread of 3-8 tweets.
Rules:
- Each tweet MUST be under 280 characters
- Separate tweets with "---" on its own line
- First tweet hooks the reader with a bold insight or question
- Last tweet has a call to action
- Use conversational, punchy tone — write like a person, not a brand
- No hashtags in tweets
- The source material is journal notes — extract the most interesting insight and build around it

After writing the thread, ALWAYS call the savePlatformContent tool with the full thread content.`,

	linkedin: `You are helping craft a LinkedIn post from the author's notes. Write a single post of 1200-1800 characters.
Rules:
- Open with a hook (question, bold claim, or surprising insight from the journal)
- Write in first person, conversational but professional
- Use short paragraphs (1-2 sentences)
- Add line breaks between paragraphs for readability
- End with a question or call to action
- No emojis in the first line
- The source material is journal notes — find the compelling narrative and shape it for a professional audience

After writing the post, ALWAYS call the savePlatformContent tool with the full post content.`,

	slack: `You are helping craft a Slack message from the author's notes. Write 800-1400 characters.
Rules:
- Use Slack mrkdwn: *bold*, _italic_, \`code\`, > quote
- Start with a one-line summary
- Break into bullet points for key insights
- Keep it scannable
- End with a discussion question
- The source material is journal notes — distill the key learnings

After writing the message, ALWAYS call the savePlatformContent tool with the full message content.`,

	ghost: `You are helping shape a blog post or newsletter from the author's journal notes.
Rules:
- Help the author find the narrative arc in their notes
- Suggest a structure: hook, story, insight, takeaway
- The content should work as a standalone newsletter or blog post
- Keep the author's voice — don't over-polish
- Ask clarifying questions if the direction isn't clear
- Focus on what makes this interesting to someone who wasn't there

After writing the post, ALWAYS call the savePlatformContent tool with the full post content.`,
};

app.post("/api/studio/chat", async (c) => {
	if (!isAgentConfigured()) {
		return c.json({ error: "ANTHROPIC_API_KEY not configured" }, 503);
	}

	const body = await c.req.json();
	const { messages, content, platform, slug } = body;

	if (!messages || !content || !platform) {
		return c.json({ error: "Missing required fields: messages, content, platform" }, 400);
	}

	const platformPrompt =
		PLATFORM_PROMPTS[platform] ?? `You are adapting content for ${platform}.

After writing the adapted content, ALWAYS call the savePlatformContent tool with the full content.`;

	const systemPrompt = `${platformPrompt}

Here are the author's source notes to work with:

---
${content}
---

Be a thoughtful collaborator. Ask questions, suggest angles, explain your choices. When you write content for the platform, call the savePlatformContent tool with it.${isImageConfigured() ? "\n\nYou can generate images to accompany the content using the generateImage tool. Generate a hero image when you write the first draft, or when the author asks for one." : ""}`;

	const result = streamText({
		model: getModel(),
		system: systemPrompt,
		messages,
		tools: {
			savePlatformContent: tool({
				description:
					"Save the adapted content for the target platform. Call this every time you write or revise content for the platform.",
				parameters: z.object({
					content: z
						.string()
						.describe("The full adapted content for the platform"),
				}),
				execute: async ({ content: adaptedContent }) => {
					// Save to content store
					if (slug) {
						const storeRecord = getContentRecord(slug);
						if (storeRecord) {
							const store = loadContentStore();
							const record = store[slug];
							if (record) {
								const existing = record.platforms[platform] ?? {
									platform,
									content: "",
									published: false,
									published_at: null,
									external_id: "",
								};
								existing.content = adaptedContent;
								record.platforms[platform] = existing;
								saveContentStore(store);
							}
						}
					}
					return { saved: true, platform, length: adaptedContent.length };
				},
			}),
			generateImage: tool({
				description:
					"Generate an image to accompany the content. Use for hero images or when the author asks.",
				parameters: z.object({
					prompt: z
						.string()
						.describe(
							"Visual metaphor description — describe the scene, not the article topic",
						),
					mood: z
						.enum([
							"reflective",
							"energetic",
							"cautionary",
							"triumphant",
							"intimate",
							"technical",
							"playful",
							"somber",
						])
						.describe("Visual mood matching the content tone"),
				}),
				execute: async ({ prompt: imagePrompt, mood }) => {
					const config = getConfig();
					const imageResult = await generateImage(imagePrompt, {
						outputDir: config.OUTPUT_DIR,
						mood,
						slug: slug ?? "studio",
					});

					if (!imageResult) {
						return { error: "Image generation not available or failed" };
					}

					// Add to content store images array
					if (slug) {
						const store = loadContentStore();
						const record = store[slug];
						if (record) {
							record.images.push({
								filename: imageResult.filename,
								role: "hero",
								prompt: imagePrompt,
								relative_path: imageResult.relativePath,
							});
							saveContentStore(store);
						}
					}

					return {
						url: `/api/studio/images/${imageResult.relativePath}`,
						alt: imagePrompt,
						mood,
					};
				},
			}),
		},
		maxSteps: 3,
	});

	return result.toDataStreamResponse();
});
```

Also move the `PLATFORM_PROMPTS` constant to be part of this section (remove the old one higher up in the file if it exists).

**Important**: Remove the old imports that are no longer needed:
- Remove: `import { callAgent, callAgentStreaming, isAgentConfigured } from "../lib/agent.js";`
- Add: `import { streamText, tool } from "ai";`
- Add: `import { getModel, isAgentConfigured } from "../lib/agent.js";`
- Add: `import { generateImage, isImageConfigured } from "../lib/images.js";`

Also remove the old `StudioChatRequestSchema` import from the schemas import line if it's only used by the old endpoints.

Remove `buildChatPrompt`, `parseChatResponse` functions entirely.

Remove the `POST /api/studio/chat/stream` endpoint entirely.

**Step 3: Verify TypeScript compiles**

```bash
cd /Users/nikpatel/Documents/GitHub/distill/web && npx tsc --noEmit
```

Expected: 0 errors

**Step 4: Verify biome passes**

```bash
cd /Users/nikpatel/Documents/GitHub/distill/web && npx biome check server/routes/studio.ts server/lib/agent.ts server/lib/images.ts
```

Expected: No errors (auto-fix if needed with `--write`)

**Step 5: Commit**

```bash
cd /Users/nikpatel/Documents/GitHub/distill
git add web/server/routes/studio.ts web/shared/schemas.ts
git commit -m "feat: replace Agent SDK chat with streamText + tools (savePlatformContent, generateImage)"
```

---

### Task 5: Rewrite `AgentChat.tsx` with `useChat()` Hook

**Files:**
- Modify: `web/src/components/studio/AgentChat.tsx` (full rewrite)

**Step 1: Rewrite the component**

Replace the entire contents of `web/src/components/studio/AgentChat.tsx` with:

```tsx
import { useChat } from "@ai-sdk/react";
import { Send } from "lucide-react";
import { useCallback, useEffect, useRef } from "react";
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

/** Convert content-store ChatMessage[] to AI SDK initialMessages format. */
function toInitialMessages(history: ChatMessage[]) {
	return history.map((msg, i) => ({
		id: `${msg.timestamp}-${i}`,
		role: msg.role as "user" | "assistant",
		content: msg.content,
	}));
}

/** Convert AI SDK messages back to content-store ChatMessage[] for persistence. */
function toStoreChatMessages(messages: Array<{ role: string; content: string }>): ChatMessage[] {
	const now = new Date().toISOString();
	return messages
		.filter((m) => m.role === "user" || m.role === "assistant")
		.map((m) => ({
			role: m.role as "user" | "assistant",
			content: typeof m.content === "string" ? m.content : "",
			timestamp: now,
		}));
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

	const { messages, input, setInput, handleSubmit, status, error } = useChat({
		api: "/api/studio/chat",
		body: { content, platform, slug },
		initialMessages: toInitialMessages(chatHistory),
		onToolCall: ({ toolCall }) => {
			if (toolCall.toolName === "savePlatformContent") {
				const args = toolCall.args as { content: string };
				if (args.content) {
					onPlatformContent(args.content);
				}
			}
			if (toolCall.toolName === "generateImage") {
				// Image result comes back in tool result, handled below
			}
		},
		onFinish: () => {
			// Persist chat history to content store
			const storeMessages = toStoreChatMessages(messages);
			onHistoryChange(storeMessages);

			// Scroll to bottom
			setTimeout(() => {
				scrollRef.current?.scrollTo({
					top: scrollRef.current.scrollHeight,
					behavior: "smooth",
				});
			}, 50);
		},
	});

	// Check tool results for image generation
	useEffect(() => {
		for (const msg of messages) {
			if (msg.role !== "assistant" || !msg.parts) continue;
			for (const part of msg.parts) {
				if (
					part.type === "tool-invocation" &&
					part.toolInvocation.toolName === "generateImage" &&
					part.toolInvocation.state === "result"
				) {
					const result = part.toolInvocation.result as { url?: string; alt?: string };
					if (result.url) {
						onImageGenerated(result.url, result.alt ?? "");
					}
				}
			}
		}
	}, [messages, onImageGenerated]);

	const handleKeyDown = (e: React.KeyboardEvent) => {
		if (e.key === "Enter" && !e.shiftKey) {
			e.preventDefault();
			handleSubmit(e as unknown as React.FormEvent);
		}
	};

	const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
		setInput(e.target.value);
		e.target.style.height = "auto";
		e.target.style.height = `${Math.min(e.target.scrollHeight, 120)}px`;
	};

	const isLoading = status === "streaming" || status === "submitted";

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
							<div
								className={`max-w-[90%] rounded-xl px-3.5 py-2.5 text-sm leading-relaxed ${
									msg.role === "user"
										? "bg-indigo-600 text-white"
										: "bg-zinc-100 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-200"
								}`}
							>
								{/* Render message parts */}
								{msg.parts?.map((part, partIdx) => {
									if (part.type === "text" && part.text) {
										return (
											<p key={`text-${partIdx}`} className="whitespace-pre-wrap">
												{part.text}
											</p>
										);
									}
									if (
										part.type === "tool-invocation" &&
										part.toolInvocation.toolName === "generateImage" &&
										part.toolInvocation.state === "result"
									) {
										const result = part.toolInvocation.result as {
											url?: string;
											alt?: string;
											error?: string;
										};
										if (result.url) {
											return (
												<img
													key={`img-${partIdx}`}
													src={result.url}
													alt={result.alt ?? "Generated image"}
													className="mt-2 max-w-full rounded-lg"
												/>
											);
										}
										if (result.error) {
											return (
												<p
													key={`err-${partIdx}`}
													className="mt-1 text-xs text-amber-600 dark:text-amber-400"
												>
													Image: {result.error}
												</p>
											);
										}
									}
									if (
										part.type === "tool-invocation" &&
										part.toolInvocation.toolName === "savePlatformContent" &&
										part.toolInvocation.state === "result"
									) {
										return (
											<p
												key={`tool-${partIdx}`}
												className="mt-1 text-xs text-emerald-600 dark:text-emerald-400"
											>
												Content saved to {platform}
											</p>
										);
									}
									return null;
								})}
								{/* Fallback for simple string content (initial messages) */}
								{!msg.parts?.length && typeof msg.content === "string" && (
									<p className="whitespace-pre-wrap">{msg.content}</p>
								)}
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
				<form onSubmit={handleSubmit} className="flex items-end gap-2">
					<textarea
						ref={inputRef}
						value={input}
						onChange={handleInput}
						onKeyDown={handleKeyDown}
						disabled={isLoading}
						placeholder={`Write or refine ${platform} content...`}
						rows={1}
						className="flex-1 resize-none rounded-xl border border-zinc-300 bg-white px-3.5 py-2.5 text-sm leading-relaxed placeholder-zinc-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-900 dark:placeholder-zinc-500"
					/>
					<button
						type="submit"
						disabled={isLoading || !input.trim()}
						className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-30"
					>
						<Send className="h-4 w-4" />
					</button>
				</form>
			</div>
		</div>
	);
}
```

**Step 2: Verify TypeScript compiles**

```bash
cd /Users/nikpatel/Documents/GitHub/distill/web && npx tsc --noEmit
```

Expected: 0 errors. If there are type issues with `msg.parts` or `toolInvocation`, adjust types to match the AI SDK's `UIMessage` type. The exact shape may need minor tweaks based on the installed version.

**Step 3: Commit**

```bash
cd /Users/nikpatel/Documents/GitHub/distill
git add web/src/components/studio/AgentChat.tsx
git commit -m "feat: rewrite AgentChat with useChat() hook — streaming + tool results"
```

---

### Task 6: Update `studio.$slug.tsx` — Simplified Parent

**Files:**
- Modify: `web/src/routes/studio.$slug.tsx`

The parent component needs to:
1. Pass `slug` to `AgentChat` (new prop)
2. Replace `onResponse` with three focused callbacks: `onPlatformContent`, `onImageGenerated`, `onHistoryChange`
3. Remove the race-condition-prone `handleChatResponse`

**Step 1: Update the component**

In `web/src/routes/studio.$slug.tsx`:

1. Find the `handleChatResponse` callback (around line 119-145). Replace it with three simpler callbacks:

```typescript
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
		// No need to save separately — the tool already saved to content store
	},
	[selectedPlatform],
);

const handleImageGenerated = useCallback(
	(_url: string, _alt: string) => {
		// Refresh the item to pick up new images from content store
		queryClient.invalidateQueries({ queryKey: ["studio-item", slug] });
	},
	[queryClient, slug],
);

const handleHistoryChange = useCallback(
	(newHistory: ChatMessage[]) => {
		setChatHistory(newHistory);
		saveChatMutation.mutate(newHistory);
	},
	[saveChatMutation],
);
```

2. Find the `<AgentChat>` JSX (around line 284). Update props:

```tsx
<AgentChat
	content={data.content}
	platform={selectedPlatform}
	slug={slug ?? ""}
	chatHistory={chatHistory}
	onPlatformContent={handlePlatformContent}
	onImageGenerated={handleImageGenerated}
	onHistoryChange={handleHistoryChange}
/>
```

3. Remove the old `handleChatResponse` callback entirely.

4. Remove the `savePlatformMutation` usage from the chat response handler (keep it for manual edits via the platform bar, if used elsewhere — check before removing).

**Step 2: Verify TypeScript compiles**

```bash
cd /Users/nikpatel/Documents/GitHub/distill/web && npx tsc --noEmit
```

Expected: 0 errors

**Step 3: Commit**

```bash
cd /Users/nikpatel/Documents/GitHub/distill
git add web/src/routes/studio.$slug.tsx
git commit -m "feat: update StudioDetail with focused chat callbacks (no race condition)"
```

---

### Task 7: Update Tests

**Files:**
- Modify: `web/server/__tests__/studio.test.ts`

**Step 1: Update chat endpoint tests**

The old tests checked `/api/studio/chat` and `/api/studio/chat/stream` separately. Now there's one endpoint. Update the chat test section:

```typescript
describe("POST /api/studio/chat", () => {
	test("rejects request without required fields", async () => {
		const res = await app.request("/api/studio/chat", {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ invalid: true }),
		});
		expect(res.status).toBe(400);
	});

	test("returns 503 when ANTHROPIC_API_KEY not set", async () => {
		const origKey = process.env["ANTHROPIC_API_KEY"];
		delete process.env["ANTHROPIC_API_KEY"];

		const res = await app.request("/api/studio/chat", {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({
				messages: [{ role: "user", content: "Make it punchier" }],
				content: "Blog post text",
				platform: "linkedin",
				slug: "test-post",
			}),
		});
		expect(res.status).toBe(503);

		if (origKey) process.env["ANTHROPIC_API_KEY"] = origKey;
	});
});
```

Remove the entire `describe("POST /api/studio/chat/stream", ...)` block.

Remove the `import * as agent from "../lib/agent.js";` if no longer needed (the 503 test now checks env directly).

**Step 2: Run all server tests**

```bash
cd /Users/nikpatel/Documents/GitHub/distill/web && bun test server/
```

Expected: All tests pass.

**Step 3: Commit**

```bash
cd /Users/nikpatel/Documents/GitHub/distill
git add web/server/__tests__/studio.test.ts
git commit -m "test: update studio tests for AI SDK chat endpoint"
```

---

### Task 8: Build Verification + Biome + Frontend Tests

**Files:**
- No new files — verification only

**Step 1: TypeScript check**

```bash
cd /Users/nikpatel/Documents/GitHub/distill/web && npx tsc --noEmit
```

Expected: 0 errors

**Step 2: Biome check**

```bash
cd /Users/nikpatel/Documents/GitHub/distill/web && npx biome check .
```

Expected: 0 errors (auto-fix with `--write` if needed)

**Step 3: Build frontend**

```bash
cd /Users/nikpatel/Documents/GitHub/distill/web && bun run build
```

Expected: Build succeeds

**Step 4: Run all tests**

```bash
cd /Users/nikpatel/Documents/GitHub/distill/web && bun test server/ && npx vitest run
```

Expected: All pass

**Step 5: Commit any remaining fixes**

```bash
cd /Users/nikpatel/Documents/GitHub/distill
git add -A web/
git commit -m "chore: fix build and lint issues from AI SDK migration"
```

---

### Task 9: Smoke Test

**Step 1: Start the server**

```bash
cd /Users/nikpatel/Documents/GitHub/distill/web
kill $(lsof -ti:6107) 2>/dev/null
NODE_ENV=production bun run server/index.ts
```

**Step 2: Test in browser**

1. Open http://localhost:6107/studio
2. Click on any content item
3. Select a platform (e.g., LinkedIn)
4. Type a message like "Write a post about the most interesting thing from these notes"
5. Verify:
   - Messages stream in real-time as chat bubbles
   - Claude's conversational response appears as a message
   - Platform content preview updates when `savePlatformContent` tool fires
   - "Content saved to linkedin" indicator shows in the chat
   - If `GOOGLE_AI_API_KEY` is set: image appears inline when generated

**Step 3: Test fallback without API key**

```bash
curl -s -X POST http://localhost:6107/api/studio/chat \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"test"}],"content":"test","platform":"x"}' | head -1
```

Expected: `{"error":"ANTHROPIC_API_KEY not configured"}` with status 503
