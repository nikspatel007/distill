import { generateObject } from "ai";
import { anthropic } from "@ai-sdk/anthropic";
import { z } from "zod";

const HighlightSchema = z.object({
  title: z.string(),
  source: z.string(),
  url: z.string(),
  summary: z.string(),
  tags: z.array(z.string()),
  imagePrompt: z.string().nullable(),
});

const DraftSchema = z.object({
  platform: z.string(),
  content: z.string(),
  charCount: z.number(),
  sourceHighlights: z.array(z.string()),
});

export interface ContentForBrief {
  title: string;
  url: string;
  summary: string;
  source: string;
  siteName: string;
  tags: string[];
}

export async function extractHighlights(items: ContentForBrief[]) {
  if (items.length === 0) return [];

  const itemList = items
    .map(
      (item, i) =>
        `${i + 1}. "${item.title}" (${item.siteName})\n   URL: ${item.url}\n   ${item.summary}`,
    )
    .join("\n\n");

  const result = await generateObject({
    model: anthropic("claude-sonnet-4-5-20250929"),
    schema: z.object({ highlights: z.array(HighlightSchema) }),
    prompt: `You are a reading brief curator. From these ${items.length} articles, pick the 3 most interesting and worth knowing about. Rank by interestingness — surprising insights, counterintuitive findings, or important developments beat incremental news.

For each highlight:
- title: the article title
- source: publication/site name
- url: the article URL
- summary: 2-3 sentence summary focused on what makes this worth knowing. Be specific, not generic.
- tags: 2-4 topic tags
- imagePrompt: a cinematic image prompt (15-20 words) that visually captures the article's core idea. Use metaphorical imagery, not literal screenshots. Or null if not visual.

Articles:
${itemList}`,
  });

  return result.object.highlights;
}

export async function generateDrafts(
  highlights: Array<{
    title: string;
    source: string;
    summary: string;
    url: string;
  }>,
  voiceRules?: string,
) {
  if (highlights.length === 0) return [];

  const highlightText = highlights
    .map((h) => `- "${h.title}" (${h.source}): ${h.summary}`)
    .join("\n");

  const voiceSection = voiceRules
    ? `\n\nApply these voice rules to the drafts:\n${voiceRules}`
    : "";

  const result = await generateObject({
    model: anthropic("claude-sonnet-4-5-20250929"),
    schema: z.object({ drafts: z.array(DraftSchema) }),
    prompt: `Generate social media draft posts from these reading highlights.

Highlights:
${highlightText}

Generate 2 drafts:
1. LinkedIn post (< 900 characters): Professional insight angle. Start with a hook, not "I just read...". Share a specific takeaway. End with a question or reflection.
2. X/Twitter post (< 280 characters): Punchy, conversational. One key insight.

For each:
- platform: "linkedin" or "x"
- content: the post text
- charCount: character count
- sourceHighlights: array of highlight titles used${voiceSection}`,
  });

  return result.object.drafts;
}

export async function findConnection(
  todayHighlights: Array<{ title: string; summary: string }>,
  pastContext: string,
) {
  if (!pastContext || todayHighlights.length === 0) return null;

  try {
    const result = await generateObject({
      model: anthropic("claude-sonnet-4-5-20250929"),
      schema: z.object({
        today: z.string(),
        past: z.string(),
        connectionType: z.string(),
        explanation: z.string(),
        strength: z.number().min(0).max(1),
      }),
      prompt: `Find the single strongest connection between today's reading and the user's past activity.

Today's highlights:
${todayHighlights.map((h) => `- ${h.title}: ${h.summary}`).join("\n")}

Past context (recent themes, sessions, threads):
${pastContext}

Find a meaningful, non-obvious connection. The best connections are:
- A reading that validates or challenges something the user built
- A pattern forming across multiple days of reading
- A topic that keeps recurring in both reading and work

Return:
- today: what from today connects
- past: what from the past it connects to
- connectionType: "validates" | "challenges" | "extends" | "pattern" | "emerging"
- explanation: 1-2 sentences explaining the connection
- strength: 0-1 confidence score`,
    });
    return result.object;
  } catch {
    return null;
  }
}
