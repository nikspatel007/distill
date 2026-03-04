# Blog

The blog pipeline synthesizes weekly and thematic blog posts from your journal entries and reading digests.

## Basic usage

```bash
uv run python -m distill blog --output ./insights
```

## Post types

### Weekly synthesis

Summarizes a week of journal entries into a cohesive blog post.

```bash
uv run python -m distill blog --output ./insights --type weekly --week 2026-W09
```

### Thematic deep-dives

Detects recurring themes across journal entries and generates focused posts.

```bash
uv run python -m distill blog --output ./insights --type thematic
```

## Configuration

```toml
[blog]
target_word_count = 1200
include_diagrams = true        # Mermaid diagrams
model = "claude-sonnet-4-6"
platforms = ["obsidian"]       # where to publish
```

## Publishing

### Obsidian (default)

Blog posts are written to `./insights/blog/` as markdown with YAML frontmatter and Obsidian wiki links.

### Ghost CMS

```bash
uv run python -m distill blog --output ./insights \
  --publish ghost \
  --ghost-url https://your-blog.ghost.io \
  --ghost-key "id:secret"
```

See [Ghost integration](../integrations/ghost.md).

### Multiple platforms

```bash
uv run python -m distill blog --output ./insights --publish obsidian,ghost,postiz
```

## Memory

The blog pipeline tracks what it has generated (`.blog-state.json`) to avoid regenerating existing posts. It also maintains cross-post memory (`.blog-memory.json`) to avoid repeating examples.

## Editorial notes

Guide the blog pipeline with editorial notes:

```bash
uv run python -m distill note "Focus on the multi-agent architecture this week" \
  --target "week:2026-W09"
```

Notes are injected into the LLM prompt for the specified target.
