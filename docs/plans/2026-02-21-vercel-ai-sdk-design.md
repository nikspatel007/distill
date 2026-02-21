# Vercel AI SDK Migration — Design

## Goal

Replace the Agent SDK (CLI subprocess) with Vercel AI SDK for Studio chat. Add tool-based image generation via Nano Banana (google-genai). Make the chat feel like a natural conversation with proper message threading, streaming, and inline images.

## Current State

- Agent SDK (`@anthropic-ai/claude-agent-sdk`) spawns Claude Code CLI processes for chat
- Custom SSE streaming with manual `ReadableStream` + `TextEncoder`
- RESPONSE/ADAPTED_CONTENT format: Claude returns both in one message, we regex-parse them apart
- Race condition: `savePlatformMutation` invalidates query, re-fetch overwrites local chat history before `saveChatMutation` completes
- Image generation exists in Python (`src/shared/images.py`) but not available in chat

## Architecture

```
User types in chat
    → useChat() hook (manages messages, streaming, state)
    → POST /api/studio/chat (Hono)
    → streamText() with @ai-sdk/anthropic
    → Claude streams response + calls tools:
        • savePlatformContent({ content }) → updates preview panel
        • generateImage({ prompt, mood }) → calls google-genai → returns image URL
    → useChat() receives text deltas + tool results
    → Messages render: text bubbles + inline images
```

## Backend Changes

### Packages

- **Add**: `ai`, `@ai-sdk/anthropic`, `@google/genai`
- **Remove**: `@anthropic-ai/claude-agent-sdk`

### `web/server/lib/agent.ts` — Rewrite

Replace Agent SDK wrapper with Anthropic SDK client:

```typescript
import { createAnthropic } from "@ai-sdk/anthropic";

export function getModel() {
  return createAnthropic()("claude-sonnet-4-5-20250929");
}

export function isAgentConfigured(): boolean {
  return !!process.env["ANTHROPIC_API_KEY"];
}
```

### `web/server/lib/images.ts` — New

Thin wrapper around `@google/genai` for image generation (mirrors Python `src/shared/images.py`):

- `isImageConfigured()` — checks `GOOGLE_AI_API_KEY`
- `generateImage(prompt, mood, outputDir)` → saves PNG, returns `{ filename, relativePath }`
- Same 8 mood-based style prefixes as Python version
- Graceful no-op when not configured

### `web/server/routes/studio.ts` — Chat Endpoints

Replace both `/api/studio/chat` and `/api/studio/chat/stream` with single endpoint:

```typescript
import { streamText, tool } from "ai";

app.post("/api/studio/chat", async (c) => {
  const { messages, content, platform, slug } = await c.req.json();

  const result = streamText({
    model: getModel(),
    system: PLATFORM_PROMPTS[platform],
    messages,
    tools: {
      savePlatformContent: tool({
        description: "Save the adapted content for the target platform",
        parameters: z.object({ content: z.string() }),
        execute: async ({ content }) => {
          // Persist to content store
          return { saved: true };
        },
      }),
      generateImage: tool({
        description: "Generate an image for the content",
        parameters: z.object({
          prompt: z.string(),
          mood: z.enum(["reflective", "energetic", ...]),
        }),
        execute: async ({ prompt, mood }) => {
          // Call google-genai, save to output dir
          return { url: "/api/studio/images/...", alt: prompt };
        },
      }),
    },
    maxSteps: 2,
  });

  return result.toDataStreamResponse();
});
```

## Frontend Changes

### `web/src/components/studio/AgentChat.tsx` — Rewrite

Replace custom streaming code with `useChat()`:

```typescript
import { useChat } from "ai/react";

const { messages, input, handleInputChange, handleSubmit, isLoading, status } = useChat({
  api: "/api/studio/chat",
  body: { content, platform, slug },
  initialMessages: chatHistory,  // Load from content store
  onFinish: (message) => {
    // Persist to content store — single callback, no race condition
  },
  onToolCall: ({ toolCall }) => {
    if (toolCall.toolName === "savePlatformContent") {
      // Update platform preview panel
    }
  },
});
```

Messages render naturally — text bubbles for conversation, images inline when `generateImage` tool returns results.

### `web/shared/schemas.ts`

- Remove `StudioStreamEventSchema` (no longer needed — AI SDK handles streaming format)
- Keep `ChatMessageSchema` for content store persistence

## Image Generation Flow

### Auto-generate (during platform adaptation)

System prompt instructs Claude: "After adapting content, generate a hero image that captures the post's theme." Claude calls `generateImage` tool, image appears in chat + gets saved to content store.

### Manual (user-triggered)

User types "generate an image showing X". Claude calls `generateImage` tool with the user's description. Image appears inline in the chat thread.

### Storage

Images saved to `{OUTPUT_DIR}/studio/images/{slug}-{timestamp}.png`. Metadata added to content store record's `images[]` array. Served via existing `GET /api/studio/images/*` endpoint.

## What Doesn't Change

- Platform prompts (PLATFORM_PROMPTS object)
- All other Studio endpoints (items, publish, platforms, status)
- Image serving endpoint (`GET /api/studio/images/*`)
- Content store schema (images already supported)
- Python `call_claude()` — unaffected

## Files Summary

| File | Action | Purpose |
|------|--------|---------|
| `web/package.json` | Modify | Add `ai`, `@ai-sdk/anthropic`, `@google/genai`; remove `@anthropic-ai/claude-agent-sdk` |
| `web/server/lib/agent.ts` | Rewrite | Anthropic model factory via `@ai-sdk/anthropic` |
| `web/server/lib/images.ts` | Create | google-genai wrapper for image generation |
| `web/server/routes/studio.ts` | Modify | Single `streamText()` chat endpoint with tools |
| `web/shared/schemas.ts` | Modify | Remove streaming event schema |
| `web/src/components/studio/AgentChat.tsx` | Rewrite | `useChat()` hook replaces custom streaming |
| `web/server/__tests__/studio.test.ts` | Modify | Mock AI SDK, test tool calls |
