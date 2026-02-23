# Studio Tools & MCP Server Design

## Goal

Make the Studio chat agent a full platform assistant by exposing distill operations as tools. Build an MCP server so external agents (Claude Code, TroopX) can use the same tools.

## Architecture

Embedded MCP server — tools are plain TS functions in `server/tools/`. Studio chat imports them directly as AI SDK `tool()` definitions. A thin MCP wrapper in `server/mcp/server.ts` exposes the same functions for external agents over stdio.

```
server/tools/              ← Pure tool functions (the real logic)
  content.ts               ← list, get, update, save, create, status
  pipeline.ts              ← run pipeline/journal/blog/intake, add seed/note
  research.ts              ← fetch URL, save to intake
  publishing.ts            ← publish, schedule, list posts, list integrations
  images.ts                ← generate image (existing, extracted)

server/mcp/                ← MCP wrapper (thin layer)
  server.ts                ← Registers tools from server/tools/* as MCP tools

Studio chat endpoint       ← Imports from server/tools/* directly, no MCP overhead
CLI: `distill mcp`         ← Spawns MCP server over stdio for external agents
```

### Why Embedded

- One process — no IPC, shared ContentStore and config
- Tools are plain functions — testable, reusable
- Any MCP client can connect (Claude Code, TroopX, other agents)
- Studio chat uses tools directly (no protocol overhead)

### Two Entry Points

```
bun run dev          → Web server (Studio chat uses tools directly)
distill mcp          → MCP stdio server (for Claude Code / agents)
```

They share the same tool code. No need to run both simultaneously.

## Tool Inventory

### Content Management (6 tools)

| Tool | Description | Inputs |
|------|-------------|--------|
| `list_content` | List all content items with filters | `type?`, `status?` |
| `get_content` | Get full content record by slug | `slug` |
| `update_source` | Rewrite the source post body | `slug`, `content`, `title?` |
| `save_platform` | Save adapted platform content | `slug`, `platform`, `content` |
| `update_status` | Change item status | `slug`, `status` |
| `create_content` | Create new content item | `title`, `body`, `type`, `tags?` |

### Pipeline (6 tools)

| Tool | Description | Inputs |
|------|-------------|--------|
| `run_pipeline` | Full pipeline: sessions → journal → intake → blog | `project?`, `skip_journal?`, `skip_intake?`, `skip_blog?` |
| `run_journal` | Generate journal entries | `project?`, `date?`, `since?`, `force?` |
| `run_blog` | Generate blog posts | `project?`, `type` (weekly/thematic/all), `week?`, `force?` |
| `run_intake` | Run content ingestion | `project?`, `sources?`, `use_defaults?` |
| `add_seed` | Add seed idea to pipeline | `text`, `tags?` |
| `add_note` | Add editorial steering note | `text`, `target?` |

All pipeline tools accept optional `project?` argument. Maps to `[[projects]]` name in `.distill.toml` → resolves to project directory. Shells out to `uv run python -m distill <command> <flags>`.

### Research (2 tools)

| Tool | Description | Inputs |
|------|-------------|--------|
| `fetch_url` | Fetch URL, extract readable text | `url` |
| `save_to_intake` | Fetch URL AND save as ContentItem | `url`, `tags?`, `notes?` |

Uses `cheerio` for text extraction (no headless browser). `save_to_intake` persists the content for future synthesis.

### Publishing (4 tools)

| Tool | Description | Inputs |
|------|-------------|--------|
| `list_integrations` | List connected Postiz platforms | (none) |
| `publish` | Publish content to platforms | `slug`, `platforms[]`, `mode`, `scheduled_at?` |
| `list_posts` | List recent/upcoming Postiz posts | `status?`, `limit?` |
| `generate_image` | Generate hero image | `prompt`, `mood` |

## Integration Points

### Studio Chat Endpoint

```typescript
// server/routes/studio.ts
import { contentTools } from "../tools/content.js";
import { pipelineTools } from "../tools/pipeline.js";
import { researchTools } from "../tools/research.js";
import { publishingTools } from "../tools/publishing.js";

const result = streamText({
  model: getModel(),
  system: systemPrompt,
  messages: modelMessages,
  tools: {
    ...contentTools(slug, platform),  // scoped to current item
    ...pipelineTools(),
    ...researchTools(),
    ...publishingTools(slug),
  },
});
```

### MCP Server

```typescript
// server/mcp/server.ts
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
// Register each tool function as an MCP tool
// Expose over stdio transport
```

### CLI Entry Point

```bash
# Claude Code / agents connect via:
distill mcp

# Or in .claude/mcp.json:
{ "distill": { "command": "uv", "args": ["run", "python", "-m", "distill", "mcp"] } }
```

## Dependencies

- `@modelcontextprotocol/sdk` — MCP server SDK (new)
- `cheerio` — HTML text extraction for research tools (new)
- Existing: `@anthropic-ai/sdk`, `ai`, `@google/genai`

## File Summary

| File | Action |
|------|--------|
| `web/server/tools/content.ts` | Create |
| `web/server/tools/pipeline.ts` | Create |
| `web/server/tools/research.ts` | Create |
| `web/server/tools/publishing.ts` | Create |
| `web/server/tools/images.ts` | Create (extract from existing) |
| `web/server/mcp/server.ts` | Create |
| `web/server/routes/studio.ts` | Modify — import tools from modules |
| `src/cli.py` | Modify — add `distill mcp` command |
| `web/package.json` | Modify — add deps |
