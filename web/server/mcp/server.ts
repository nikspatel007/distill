/**
 * MCP Server — exposes distill tools over Model Context Protocol.
 *
 * Used by Claude Code CLI and external agents via stdio transport.
 * Wraps the same tool functions used by Studio chat.
 */
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

import {
	createContent,
	deleteContent,
	getContent,
	listContent,
	savePlatform,
	updateSource,
	updateStatus,
} from "../tools/content.js";
import { generateImage, isImageConfigured } from "../tools/images.js";
import {
	addNote,
	addSeed,
	runBlog,
	runIntake,
	runJournal,
	runPipeline,
} from "../tools/pipeline.js";
import { listPostizIntegrations, listPostizPosts, publishContent } from "../tools/publishing.js";
import { fetchUrl, saveToIntake } from "../tools/research.js";

export function createMcpServer(): McpServer {
	const server = new McpServer({
		name: "distill",
		version: "1.0.0",
	});

	// --- Content ---
	server.tool(
		"list_content",
		"List all content items in the studio. Optional filters: type, status.",
		{ type: z.string().optional(), status: z.string().optional() },
		async (params) => ({
			content: [{ type: "text" as const, text: JSON.stringify(await listContent(params)) }],
		}),
	);

	server.tool(
		"get_content",
		"Get full content record by slug.",
		{ slug: z.string() },
		async (params) => ({
			content: [{ type: "text" as const, text: JSON.stringify(await getContent(params)) }],
		}),
	);

	server.tool(
		"update_source",
		"Update the source post content (body and optionally title).",
		{ slug: z.string(), content: z.string(), title: z.string().optional() },
		async (params) => ({
			content: [{ type: "text" as const, text: JSON.stringify(await updateSource(params)) }],
		}),
	);

	server.tool(
		"save_platform",
		"Save adapted content for a specific platform.",
		{ slug: z.string(), platform: z.string(), content: z.string() },
		async (params) => ({
			content: [{ type: "text" as const, text: JSON.stringify(await savePlatform(params)) }],
		}),
	);

	server.tool(
		"update_status",
		"Change content status (draft, review, ready, published, archived).",
		{
			slug: z.string(),
			status: z.enum(["draft", "review", "ready", "published", "archived"]),
		},
		async (params) => ({
			content: [{ type: "text" as const, text: JSON.stringify(await updateStatus(params)) }],
		}),
	);

	server.tool(
		"create_content",
		"Create a new content item in the studio.",
		{
			title: z.string(),
			body: z.string(),
			content_type: z.enum(["weekly", "thematic", "journal", "digest", "seed"]),
			tags: z.array(z.string()).optional(),
		},
		async (params) => ({
			content: [{ type: "text" as const, text: JSON.stringify(await createContent(params)) }],
		}),
	);

	server.tool(
		"delete_content",
		"Delete a content item permanently.",
		{ slug: z.string() },
		async (params) => ({
			content: [{ type: "text" as const, text: JSON.stringify(await deleteContent(params)) }],
		}),
	);

	// --- Pipeline ---
	server.tool(
		"run_pipeline",
		"Run the full distill pipeline: sessions -> journal -> intake -> blog.",
		{
			project: z.string().optional(),
			skip_journal: z.boolean().optional(),
			skip_intake: z.boolean().optional(),
			skip_blog: z.boolean().optional(),
		},
		async (params) => ({
			content: [{ type: "text" as const, text: JSON.stringify(await runPipeline(params)) }],
		}),
	);

	server.tool(
		"run_journal",
		"Generate journal entries from coding sessions.",
		{
			project: z.string().optional(),
			date: z.string().optional(),
			since: z.string().optional(),
			force: z.boolean().optional(),
		},
		async (params) => ({
			content: [{ type: "text" as const, text: JSON.stringify(await runJournal(params)) }],
		}),
	);

	server.tool(
		"run_blog",
		"Generate blog posts from journal entries.",
		{
			project: z.string().optional(),
			type: z.string().optional(),
			week: z.string().optional(),
			force: z.boolean().optional(),
		},
		async (params) => ({
			content: [{ type: "text" as const, text: JSON.stringify(await runBlog(params)) }],
		}),
	);

	server.tool(
		"run_intake",
		"Run content ingestion from RSS feeds, browser history, etc.",
		{
			project: z.string().optional(),
			sources: z.string().optional(),
			use_defaults: z.boolean().optional(),
		},
		async (params) => ({
			content: [{ type: "text" as const, text: JSON.stringify(await runIntake(params)) }],
		}),
	);

	server.tool(
		"add_seed",
		"Add a seed idea to the pipeline for future blog posts.",
		{ text: z.string(), tags: z.string().optional() },
		async (params) => ({
			content: [{ type: "text" as const, text: JSON.stringify(await addSeed(params)) }],
		}),
	);

	server.tool(
		"add_note",
		"Add an editorial note to steer content direction.",
		{ text: z.string(), target: z.string().optional() },
		async (params) => ({
			content: [{ type: "text" as const, text: JSON.stringify(await addNote(params)) }],
		}),
	);

	// --- Research ---
	server.tool(
		"fetch_url",
		"Fetch a URL and extract readable text content.",
		{ url: z.string() },
		async (params) => ({
			content: [{ type: "text" as const, text: JSON.stringify(await fetchUrl(params)) }],
		}),
	);

	server.tool(
		"save_to_intake",
		"Fetch a URL and save the content to the intake pipeline.",
		{ url: z.string(), tags: z.array(z.string()).optional(), notes: z.string().optional() },
		async (params) => ({
			content: [{ type: "text" as const, text: JSON.stringify(await saveToIntake(params)) }],
		}),
	);

	// --- Publishing ---
	server.tool(
		"list_integrations",
		"List connected Postiz platform integrations.",
		{},
		async () => ({
			content: [{ type: "text" as const, text: JSON.stringify(await listPostizIntegrations()) }],
		}),
	);

	server.tool(
		"publish",
		"Publish content to social platforms via Postiz.",
		{
			slug: z.string(),
			platforms: z.array(z.string()),
			mode: z.enum(["draft", "schedule", "now"]),
			scheduled_at: z.string().optional(),
		},
		async (params) => ({
			content: [{ type: "text" as const, text: JSON.stringify(await publishContent(params)) }],
		}),
	);

	server.tool(
		"list_posts",
		"List recent and upcoming posts from Postiz.",
		{ status: z.string().optional(), limit: z.number().optional() },
		async (params) => ({
			content: [{ type: "text" as const, text: JSON.stringify(await listPostizPosts(params)) }],
		}),
	);

	// --- Images ---
	if (isImageConfigured()) {
		server.tool(
			"generate_image",
			"Generate a hero image for content.",
			{
				prompt: z.string(),
				mood: z.enum([
					"reflective",
					"energetic",
					"cautionary",
					"triumphant",
					"intimate",
					"technical",
					"playful",
					"somber",
				]),
				slug: z.string().optional(),
			},
			async (params) => ({
				content: [{ type: "text" as const, text: JSON.stringify(await generateImage(params)) }],
			}),
		);
	}

	return server;
}

/**
 * Start MCP server over stdio transport.
 * Called from CLI: `distill mcp`
 */
export async function startMcpServer(): Promise<void> {
	const server = createMcpServer();
	const transport = new StdioServerTransport();
	await server.connect(transport);
}
