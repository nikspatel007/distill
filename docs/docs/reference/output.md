# Output Structure

After running the pipeline, your output directory (default `./insights`) contains:

```
insights/
├── intake/                          # Daily reading digests
│   └── 2026-03-04.md
│
├── journal/                         # Dev journal entries
│   └── 2026-03-04.md
│
├── blog/                            # Blog posts
│   ├── weekly-2026-W09.md
│   └── multi-agent-patterns.md      # Thematic posts
│
├── sessions/                        # Per-session Obsidian notes
│   └── session-note.md
│
├── daily/                           # Daily session summaries
│   └── daily-2026-03-04.md
│
├── weekly/                          # Weekly session digests
│   └── week-2026-W09.md
│
├── projects/                        # Per-project notes
│   └── my-project.md
│
├── brainstorm/                      # Content ideas
│   └── 2026-03-04.json
│
├── index.md                         # Session index
│
# State files (hidden, managed automatically):
├── .distill-memory.json             # Unified cross-pipeline memory
├── .distill-seeds.json              # Seed ideas
├── .distill-shares.json             # Shared URLs
├── .distill-notes.json              # Editorial notes
├── .distill-content-store.json      # Vector store (JSON fallback)
├── .distill-graph.json              # Knowledge graph
├── .intake-state.json               # Intake deduplication
├── .distill-last-run.json           # Last pipeline run report
├── .daily-social-state.json         # Social post state
├── .working-memory.json             # Journal memory
├── .intake-memory.json              # Intake memory
├── .blog-state.json                 # Blog generation state
└── .blog-memory.json                # Blog cross-post memory
```

## Obsidian integration

The default publisher uses Obsidian-compatible markdown:

- YAML frontmatter with tags, dates, and metadata
- `[[Wiki links]]` for cross-referencing
- Mermaid code blocks for diagrams

Drop the `insights/` folder into an Obsidian vault and everything links together.

## State files

State files (prefixed with `.`) are managed automatically. They track:

- Which articles have been processed (deduplication)
- Cross-session memory (themes, entities, trends)
- Blog generation state (which posts exist)
- Seeds and shares (pending vs used)

You can safely delete any state file to reset that subsystem. The pipeline will rebuild from scratch on the next run.
