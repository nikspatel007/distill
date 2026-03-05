/**
 * Zod schemas — single source of truth for all data types.
 * Used by server for validation and by frontend for type inference.
 */
import { z } from "zod";

// --- Unified Memory ---

export const DailyEntrySchema = z.object({
	date: z.string(), // ISO date string
	sessions: z.array(z.string()).default([]),
	reads: z.array(z.string()).default([]),
	themes: z.array(z.string()).default([]),
	insights: z.array(z.string()).default([]),
	decisions: z.array(z.string()).default([]),
	open_questions: z.array(z.string()).default([]),
});

export const MemoryThreadSchema = z.object({
	name: z.string(),
	summary: z.string(),
	first_seen: z.string(),
	last_seen: z.string(),
	mention_count: z.number().default(1),
	status: z.string().default("active"),
});

export const EntityRecordSchema = z.object({
	name: z.string(),
	entity_type: z.string(),
	first_seen: z.string(),
	last_seen: z.string(),
	mention_count: z.number().default(1),
	context: z.array(z.string()).default([]),
});

export const PublishedRecordSchema = z.object({
	slug: z.string(),
	title: z.string(),
	post_type: z.string(),
	date: z.string(),
	platforms: z.array(z.string()).default([]),
});

export const UnifiedMemorySchema = z.object({
	entries: z.array(DailyEntrySchema).default([]),
	threads: z.array(MemoryThreadSchema).default([]),
	entities: z.record(z.string(), EntityRecordSchema).default({}),
	published: z.array(PublishedRecordSchema).default([]),
});

// --- Blog Memory ---

export const BlogPostSummarySchema = z.object({
	slug: z.string(),
	title: z.string(),
	post_type: z.string(),
	date: z.string(),
	key_points: z.array(z.string()).default([]),
	themes_covered: z.array(z.string()).default([]),
	examples_used: z.array(z.string()).default([]),
	platforms_published: z.array(z.string()).default([]),
	postiz_ids: z.array(z.string()).default([]),
});

export const BlogMemorySchema = z.object({
	posts: z.array(BlogPostSummarySchema).default([]),
});

// --- Blog State ---

export const BlogPostRecordSchema = z.object({
	slug: z.string(),
	post_type: z.string(),
	generated_at: z.string(),
	source_dates: z.array(z.string()).default([]),
	file_path: z.string().default(""),
});

export const BlogStateSchema = z.object({
	posts: z.array(BlogPostRecordSchema).default([]),
});

// --- Seeds ---

export const SeedIdeaSchema = z.object({
	id: z.string(),
	text: z.string(),
	tags: z.array(z.string()).default([]),
	created_at: z.string(),
	used: z.boolean().default(false),
	used_in: z.string().nullable().default(null),
});

export const CreateSeedSchema = z.object({
	text: z.string().min(1),
	tags: z.array(z.string()).default([]),
});

// --- Shares ---

export const ShareItemSchema = z.object({
	id: z.string(),
	url: z.string(),
	note: z.string().default(""),
	tags: z.array(z.string()).default([]),
	created_at: z.string(),
	used: z.boolean().default(false),
	used_in: z.string().nullable().default(null),
	title: z.string().default(""),
	author: z.string().default(""),
	excerpt: z.string().default(""),
});

export const CreateShareSchema = z.object({
	url: z.string().min(1),
	note: z.string().default(""),
	tags: z.array(z.string()).default([]),
});

// --- Knowledge Graph ---

export const NodeTypeEnum = z.enum([
	"session", "project", "file", "entity", "thread",
	"artifact", "goal", "problem", "decision", "insight",
]);

export const EdgeTypeEnum = z.enum([
	"modifies", "reads", "executes_in", "uses", "produces",
	"leads_to", "motivated_by", "blocked_by", "solved_by",
	"informed_by", "implements", "co_occurs", "part_of",
	"related_to", "references", "depends_on", "pivoted_from",
	"evolved_into",
]);

export const GraphNodeSchema = z.object({
	id: z.string(),
	node_type: NodeTypeEnum,
	name: z.string(),
	properties: z.record(z.unknown()).default({}),
	first_seen: z.string(),
	last_seen: z.string(),
});

export const GraphEdgeSchema = z.object({
	id: z.string(),
	source_key: z.string(),
	target_key: z.string(),
	edge_type: EdgeTypeEnum,
	weight: z.number().default(1),
	properties: z.record(z.unknown()).default({}),
});

export const GraphSessionSchema = z.object({
	id: z.string(),
	summary: z.string(),
	hours_ago: z.number(),
	project: z.string(),
	goal: z.string(),
	files_modified: z.array(z.string()),
	files_read: z.array(z.string()),
	problems: z.array(z.object({
		error: z.string(),
		command: z.string(),
		resolved: z.boolean(),
	})),
	entities: z.array(z.string()),
});

export const GraphActivityResponseSchema = z.object({
	project: z.string(),
	time_window_hours: z.number(),
	sessions: z.array(GraphSessionSchema),
	top_entities: z.array(z.object({ name: z.string(), count: z.number() })),
	active_files: z.array(z.object({ path: z.string(), hours_ago: z.number() })),
	stats: z.object({
		session_count: z.number(),
		avg_files_per_session: z.number(),
		total_problems: z.number(),
	}),
});

export const GraphNodesResponseSchema = z.object({
	nodes: z.array(GraphNodeSchema),
	edges: z.array(GraphEdgeSchema),
});

export const CouplingClusterSchema = z.object({
	files: z.array(z.string()),
	co_modification_count: z.number(),
	description: z.string().default(""),
});

export const ErrorHotspotSchema = z.object({
	file: z.string(),
	problem_count: z.number(),
	recent_problems: z.array(z.string()),
});

export const ScopeWarningSchema = z.object({
	session_name: z.string(),
	files_modified: z.number(),
	project: z.string().default(""),
	problems_hit: z.number().default(0),
});

export const RecurringProblemSchema = z.object({
	pattern: z.string(),
	occurrence_count: z.number(),
	sessions: z.array(z.string()),
});

export const GraphInsightsResponseSchema = z.object({
	date: z.string(),
	coupling_clusters: z.array(CouplingClusterSchema),
	error_hotspots: z.array(ErrorHotspotSchema),
	scope_warnings: z.array(ScopeWarningSchema),
	recurring_problems: z.array(RecurringProblemSchema),
	session_count: z.number(),
	avg_files_per_session: z.number(),
	total_problems: z.number(),
});

export const GraphAboutResponseSchema = z.object({
	focus: z.object({
		name: z.string(),
		type: z.string(),
		summary: z.string(),
	}).nullable(),
	neighbors: z.array(z.object({
		name: z.string(),
		type: z.string(),
		relevance: z.number(),
		last_seen: z.string(),
	})),
	edges: z.array(z.object({
		type: z.string(),
		source: z.string(),
		target: z.string(),
		weight: z.number(),
	})),
});

export const GraphStatsResponseSchema = z.object({
	total_nodes: z.number(),
	total_edges: z.number(),
	nodes_by_type: z.record(z.string(), z.number()),
	edges_by_type: z.record(z.string(), z.number()),
});

// --- Executive Briefing ---
export const BriefingAreaSchema = z.object({
	name: z.string(),
	status: z.enum(["active", "cooling", "emerging"]),
	momentum: z.enum(["accelerating", "steady", "decelerating"]),
	headline: z.string().default(""),
	sessions: z.number().default(0),
	reading_count: z.number().default(0),
	open_threads: z.array(z.string()).default([]),
});

export const BriefingLearningSchema = z.object({
	topic: z.string(),
	reading_count: z.number().default(0),
	connection: z.string().default(""),
	status: z.enum(["active", "emerging", "cooling"]),
});

export const BriefingRiskSchema = z.object({
	severity: z.enum(["high", "medium", "low"]),
	headline: z.string(),
	detail: z.string().default(""),
	project: z.string().default(""),
});

export const BriefingRecommendationSchema = z.object({
	priority: z.number(),
	action: z.string(),
	rationale: z.string().default(""),
});

export const BriefingResponseSchema = z.object({
	date: z.string(),
	generated_at: z.string(),
	time_window_hours: z.number(),
	summary: z.string(),
	areas: z.array(BriefingAreaSchema),
	learning: z.array(BriefingLearningSchema),
	risks: z.array(BriefingRiskSchema),
	recommendations: z.array(BriefingRecommendationSchema),
});

// --- Editorial Notes ---

export const EditorialNoteSchema = z.object({
	id: z.string(),
	text: z.string(),
	target: z.string().default(""),
	created_at: z.string(),
	used: z.boolean().default(false),
});

export const CreateNoteSchema = z.object({
	text: z.string().min(1),
	target: z.string().default(""),
});

// --- Journal Frontmatter ---

export const JournalFrontmatterSchema = z.object({
	date: z.string(),
	type: z.string().default("journal"),
	style: z.string().default("dev-journal"),
	sessions_count: z.number().default(0),
	duration_minutes: z.number().default(0),
	tags: z.array(z.string()).default([]),
	projects: z.array(z.string()).default([]),
	brief: z.array(z.string()).default([]),
	created: z.string().optional(),
});

// --- Blog Frontmatter ---

export const BlogFrontmatterSchema = z.object({
	title: z.string().optional(),
	date: z.string().optional(),
	type: z.string().default("blog"),
	post_type: z.string().optional(),
	week: z.string().optional(),
	slug: z.string().optional(),
	tags: z.array(z.string()).default([]),
	themes: z.array(z.string()).default([]),
	projects: z.array(z.string()).default([]),
	created: z.string().optional(),
});

// --- Intake Frontmatter ---

export const IntakeFrontmatterSchema = z.object({
	date: z.string().optional(),
	type: z.string().default("intake"),
	sources: z.array(z.string()).default([]),
	item_count: z.number().default(0),
	tags: z.array(z.string()).default([]),
	highlights: z.array(z.string()).default([]),
	items: z.number().default(0),
	created: z.string().optional(),
});

// --- API Response types ---

export const DashboardResponseSchema = z.object({
	journalCount: z.number(),
	blogCount: z.number(),
	intakeCount: z.number(),
	pendingPublish: z.number(),
	projectCount: z.number(),
	activeProjects: z.array(
		z.object({
			name: z.string(),
			lastSeen: z.string(),
			journalCount: z.number(),
		}),
	),
	recentJournals: z.array(
		z.object({
			date: z.string(),
			style: z.string(),
			sessionsCount: z.number(),
			durationMinutes: z.number(),
			projects: z.array(z.string()),
		}),
	),
	activeThreads: z.array(MemoryThreadSchema),
	recentlyPublished: z.array(PublishedRecordSchema),
	seedCount: z.number(),
	shareCount: z.number(),
	activeNoteCount: z.number(),
});

export const JournalEntrySchema = z.object({
	date: z.string(),
	style: z.string(),
	sessionsCount: z.number(),
	durationMinutes: z.number(),
	tags: z.array(z.string()),
	projects: z.array(z.string()),
	filename: z.string(),
});

export const JournalDetailSchema = z.object({
	meta: JournalEntrySchema,
	content: z.string(),
});

export const BlogPostSchema = z.object({
	slug: z.string(),
	title: z.string(),
	postType: z.string(),
	date: z.string(),
	tags: z.array(z.string()),
	themes: z.array(z.string()),
	projects: z.array(z.string()),
	filename: z.string(),
	platformsPublished: z.array(z.string()),
});

export const BlogDetailSchema = z.object({
	meta: BlogPostSchema,
	content: z.string(),
	images: z
		.array(
			z.object({
				filename: z.string(),
				role: z.string(),
				prompt: z.string().default(""),
				relative_path: z.string().default(""),
			}),
		)
		.default([]),
});

export const IntakeDigestSchema = z.object({
	date: z.string(),
	sources: z.array(z.string()),
	itemCount: z.number(),
	tags: z.array(z.string()),
	filename: z.string(),
});

export const IntakeDetailSchema = z.object({
	meta: IntakeDigestSchema,
	content: z.string(),
});

// --- Content Items (intake archive) ---

export const ContentItemSchema = z.object({
	id: z.string(),
	url: z.string().default(""),
	title: z.string().default(""),
	excerpt: z.string().default(""),
	word_count: z.number().default(0),
	author: z.string().default(""),
	site_name: z.string().default(""),
	source: z.string(),
	content_type: z.string().default("article"),
	tags: z.array(z.string()).default([]),
	topics: z.array(z.string()).default([]),
	published_at: z.string().nullable().default(null),
	saved_at: z.string().default(""),
	metadata: z.record(z.string(), z.unknown()).default({}),
});

export const ContentItemsResponseSchema = z.object({
	date: z.string(),
	item_count: z.number(),
	items: z.array(ContentItemSchema),
	available_sources: z.array(z.string()).default([]),
	page: z.number().default(1),
	total_pages: z.number().default(1),
	total_items: z.number().default(0),
});

export const PublishQueueItemSchema = z.object({
	slug: z.string(),
	title: z.string(),
	postType: z.string(),
	date: z.string(),
	platform: z.string(),
	published: z.boolean(),
});

export const PublishRequestSchema = z.object({
	platform: z.string(),
	mode: z.enum(["draft", "schedule", "now"]).default("draft"),
	integrationId: z.string().optional(),
});

export const PostizIntegrationSchema = z.object({
	id: z.string(),
	name: z.string(),
	provider: z.string(),
	identifier: z.string().default(""),
});

// --- Distill Config (mirrors Python DistillConfig) ---

export const OutputConfigSchema = z.object({
	directory: z.string().default("./insights"),
});

export const SessionsConfigSchema = z.object({
	sources: z.array(z.string()).default(["claude", "codex"]),
	include_global: z.boolean().default(false),
	since_days: z.number().default(2),
});

export const JournalConfigSchema = z.object({
	style: z.string().default("dev-journal"),
	target_word_count: z.number().default(600),
	model: z.string().nullable().default(null),
	memory_window_days: z.number().default(7),
});

export const BlogConfigSchema = z.object({
	target_word_count: z.number().default(1200),
	include_diagrams: z.boolean().default(true),
	model: z.string().nullable().default(null),
	platforms: z.array(z.string()).default(["obsidian"]),
});

export const IntakeConfigSchema = z.object({
	feeds_file: z.string().default(""),
	opml_file: z.string().default(""),
	use_defaults: z.boolean().default(true),
	browser_history: z.boolean().default(false),
	substack_blogs: z.array(z.string()).default([]),
	rss_feeds: z.array(z.string()).default([]),
	target_word_count: z.number().default(800),
	model: z.string().nullable().default(null),
	publishers: z.array(z.string()).default(["obsidian"]),
});

export const GhostConfigSchema = z.object({
	url: z.string().default(""),
	admin_api_key: z.string().default(""),
	newsletter_slug: z.string().default(""),
	auto_publish: z.boolean().default(true),
});

export const PostizConfigSchema = z.object({
	url: z.string().default(""),
	api_key: z.string().default(""),
	default_type: z.string().default("draft"),
	schedule_enabled: z.boolean().default(false),
});

export const RedditConfigSchema = z.object({
	client_id: z.string().default(""),
	client_secret: z.string().default(""),
	username: z.string().default(""),
});

export const YouTubeConfigSchema = z.object({
	api_key: z.string().default(""),
});

export const NotificationsConfigSchema = z.object({
	slack_webhook: z.string().default(""),
	ntfy_url: z.string().default(""),
	ntfy_topic: z.string().default("distill"),
	enabled: z.boolean().default(true),
});

export const ProjectConfigSchema = z.object({
	name: z.string(),
	description: z.string(),
	url: z.string().default(""),
	tags: z.array(z.string()).default([]),
});

export const DistillConfigSchema = z.object({
	output: OutputConfigSchema.default({}),
	sessions: SessionsConfigSchema.default({}),
	journal: JournalConfigSchema.default({}),
	blog: BlogConfigSchema.default({}),
	intake: IntakeConfigSchema.default({}),
	ghost: GhostConfigSchema.default({}),
	postiz: PostizConfigSchema.default({}),
	reddit: RedditConfigSchema.default({}),
	youtube: YouTubeConfigSchema.default({}),
	notifications: NotificationsConfigSchema.default({}),
	projects: z.array(ProjectConfigSchema).default([]),
});

// --- Source Status ---

export const SourceStatusSchema = z.object({
	source: z.string(),
	configured: z.boolean(),
	label: z.string(),
	description: z.string().default(""),
	availability: z.enum(["available", "coming_soon"]).default("available"),
});

// --- Pipeline Status ---

export const PipelineStatusSchema = z.object({
	status: z.enum(["idle", "running", "completed", "failed"]),
	log: z.string().default(""),
	startedAt: z.string().nullable().default(null),
	completedAt: z.string().nullable().default(null),
	error: z.string().nullable().default(null),
});

export const PipelineRunResponseSchema = z.object({
	id: z.string(),
	started: z.boolean(),
});

// --- Project views ---

export const ProjectSummarySchema = z.object({
	name: z.string(),
	description: z.string(),
	url: z.string().default(""),
	tags: z.array(z.string()).default([]),
	journalCount: z.number(),
	blogCount: z.number(),
	totalSessions: z.number(),
	totalDurationMinutes: z.number(),
	lastSeen: z.string(),
	hasProjectNote: z.boolean(),
});

export const ProjectDetailSchema = z.object({
	summary: ProjectSummarySchema,
	journals: z.array(JournalEntrySchema),
	blogs: z.array(BlogPostSchema),
	projectNoteContent: z.string().nullable(),
	projectJournals: z.array(JournalEntrySchema).default([]),
});

// --- Content Calendar ---

export const ContentIdeaSchema = z.object({
	title: z.string(),
	angle: z.string(),
	source_url: z.string(),
	platform: z.string(),
	rationale: z.string(),
	pillars: z.array(z.string()).default([]),
	tags: z.array(z.string()).default([]),
	status: z.string().default("pending"),
	ghost_post_id: z.string().nullable().default(null),
});

export const ContentCalendarSchema = z.object({
	date: z.string(),
	ideas: z.array(ContentIdeaSchema).default([]),
});

// --- Reading Item Brief (for Dashboard) ---

export const ReadingItemBriefSchema = z.object({
	id: z.string(),
	title: z.string(),
	url: z.string(),
	source: z.string(),
	excerpt: z.string().default(""),
	site_name: z.string().default(""),
	word_count: z.number().default(0),
});

// --- Reading Brief ---

export const ReadingHighlightSchema = z.object({
	title: z.string(),
	source: z.string(),
	url: z.string().default(""),
	summary: z.string(),
	tags: z.array(z.string()).default([]),
});

export const DraftPostSchema = z.object({
	platform: z.string(),
	content: z.string(),
	char_count: z.number().default(0),
	source_highlights: z.array(z.string()).default([]),
});

export const ReadingBriefSchema = z.object({
	date: z.string(),
	generated_at: z.string().default(""),
	highlights: z.array(ReadingHighlightSchema).default([]),
	drafts: z.array(DraftPostSchema).default([]),
});

// --- Daily Briefing ---

export const JournalBriefSchema = z.object({
	brief: z.array(z.string()),
	hasFullEntry: z.boolean(),
	date: z.string(),
	sessionsCount: z.number().default(0),
	durationMinutes: z.number().default(0),
});

export const IntakeBriefSchema = z.object({
	highlights: z.array(z.string()),
	itemCount: z.number(),
	hasFullDigest: z.boolean(),
	date: z.string(),
});

export const BriefingPublishItemSchema = z.object({
	slug: z.string(),
	title: z.string(),
	type: z.string(),
	status: z.enum(["draft", "approved", "published"]),
	platforms_ready: z.number().default(0),
	platforms_published: z.number().default(0),
	platforms_total: z.number().default(0),
});

export const DailyBriefingSchema = z.object({
	date: z.string(),
	journal: JournalBriefSchema,
	intake: IntakeBriefSchema,
	publishQueue: z.array(BriefingPublishItemSchema),
	seeds: z.array(SeedIdeaSchema),
	readingItems: z.array(ReadingItemBriefSchema).default([]),
	readingBrief: ReadingBriefSchema.nullable().default(null),
});

// --- Save (edit) ---

export const SaveMarkdownSchema = z.object({
	content: z.string(),
});

export type SaveMarkdown = z.infer<typeof SaveMarkdownSchema>;

// --- Inferred types ---

export type DailyEntry = z.infer<typeof DailyEntrySchema>;
export type MemoryThread = z.infer<typeof MemoryThreadSchema>;
export type EntityRecord = z.infer<typeof EntityRecordSchema>;
export type PublishedRecord = z.infer<typeof PublishedRecordSchema>;
export type UnifiedMemory = z.infer<typeof UnifiedMemorySchema>;
export type BlogPostSummary = z.infer<typeof BlogPostSummarySchema>;
export type BlogMemory = z.infer<typeof BlogMemorySchema>;
export type BlogPostRecord = z.infer<typeof BlogPostRecordSchema>;
export type BlogState = z.infer<typeof BlogStateSchema>;
export type SeedIdea = z.infer<typeof SeedIdeaSchema>;
export type CreateSeed = z.infer<typeof CreateSeedSchema>;
export type ShareItem = z.infer<typeof ShareItemSchema>;
export type CreateShare = z.infer<typeof CreateShareSchema>;
export type EditorialNote = z.infer<typeof EditorialNoteSchema>;
export type CreateNote = z.infer<typeof CreateNoteSchema>;
export type JournalFrontmatter = z.infer<typeof JournalFrontmatterSchema>;
export type BlogFrontmatter = z.infer<typeof BlogFrontmatterSchema>;
export type IntakeFrontmatter = z.infer<typeof IntakeFrontmatterSchema>;
export type DashboardResponse = z.infer<typeof DashboardResponseSchema>;
export type JournalEntry = z.infer<typeof JournalEntrySchema>;
export type JournalDetail = z.infer<typeof JournalDetailSchema>;
export type BlogPost = z.infer<typeof BlogPostSchema>;
export type BlogDetail = z.infer<typeof BlogDetailSchema>;
export type IntakeDigest = z.infer<typeof IntakeDigestSchema>;
export type IntakeDetail = z.infer<typeof IntakeDetailSchema>;
export type PublishQueueItem = z.infer<typeof PublishQueueItemSchema>;
export type PublishRequest = z.infer<typeof PublishRequestSchema>;
export type PostizIntegration = z.infer<typeof PostizIntegrationSchema>;
export type OutputConfig = z.infer<typeof OutputConfigSchema>;
export type SessionsConfig = z.infer<typeof SessionsConfigSchema>;
export type JournalConfig = z.infer<typeof JournalConfigSchema>;
export type BlogConfig = z.infer<typeof BlogConfigSchema>;
export type IntakeConfig = z.infer<typeof IntakeConfigSchema>;
export type GhostConfig = z.infer<typeof GhostConfigSchema>;
export type PostizConfig = z.infer<typeof PostizConfigSchema>;
export type RedditConfig = z.infer<typeof RedditConfigSchema>;
export type YouTubeConfig = z.infer<typeof YouTubeConfigSchema>;
export type NotificationsConfig = z.infer<typeof NotificationsConfigSchema>;
export type ProjectConfig = z.infer<typeof ProjectConfigSchema>;
export type DistillConfig = z.infer<typeof DistillConfigSchema>;
export type SourceStatus = z.infer<typeof SourceStatusSchema>;
export type PipelineStatus = z.infer<typeof PipelineStatusSchema>;
export type PipelineRunResponse = z.infer<typeof PipelineRunResponseSchema>;
export type ProjectSummary = z.infer<typeof ProjectSummarySchema>;
export type ProjectDetail = z.infer<typeof ProjectDetailSchema>;
export type ContentIdea = z.infer<typeof ContentIdeaSchema>;
export type ContentCalendar = z.infer<typeof ContentCalendarSchema>;
export type JournalBrief = z.infer<typeof JournalBriefSchema>;
export type IntakeBrief = z.infer<typeof IntakeBriefSchema>;
export type ReadingItemBrief = z.infer<typeof ReadingItemBriefSchema>;
export type BriefingPublishItem = z.infer<typeof BriefingPublishItemSchema>;
export type DailyBriefing = z.infer<typeof DailyBriefingSchema>;
export type ReadingHighlight = z.infer<typeof ReadingHighlightSchema>;
export type DraftPost = z.infer<typeof DraftPostSchema>;
export type ReadingBrief = z.infer<typeof ReadingBriefSchema>;
export type ContentItem = z.infer<typeof ContentItemSchema>;
export type ContentItemsResponse = z.infer<typeof ContentItemsResponseSchema>;
export type GraphNode = z.infer<typeof GraphNodeSchema>;
export type GraphEdge = z.infer<typeof GraphEdgeSchema>;
export type GraphSession = z.infer<typeof GraphSessionSchema>;
export type GraphActivityResponse = z.infer<typeof GraphActivityResponseSchema>;
export type GraphNodesResponse = z.infer<typeof GraphNodesResponseSchema>;
export type GraphInsightsResponse = z.infer<typeof GraphInsightsResponseSchema>;
export type GraphAboutResponse = z.infer<typeof GraphAboutResponseSchema>;
export type GraphStatsResponse = z.infer<typeof GraphStatsResponseSchema>;
export type BriefingArea = z.infer<typeof BriefingAreaSchema>;
export type BriefingLearning = z.infer<typeof BriefingLearningSchema>;
export type BriefingRisk = z.infer<typeof BriefingRiskSchema>;
export type BriefingRecommendation = z.infer<typeof BriefingRecommendationSchema>;
export type BriefingResponse = z.infer<typeof BriefingResponseSchema>;
export type CouplingCluster = z.infer<typeof CouplingClusterSchema>;
export type ErrorHotspot = z.infer<typeof ErrorHotspotSchema>;
export type ScopeWarning = z.infer<typeof ScopeWarningSchema>;
export type RecurringProblem = z.infer<typeof RecurringProblemSchema>;

// --- Content Store ---

export const ContentStoreImageSchema = z.object({
	filename: z.string(),
	role: z.string(),
	prompt: z.string().default(""),
	relative_path: z.string().default(""),
});

export const ContentStorePlatformSchema = z.object({
	platform: z.string(),
	content: z.string().default(""),
	published: z.boolean().default(false),
	published_at: z.string().nullable().default(null),
	external_id: z.string().default(""),
});

export const ContentStoreChatMessageSchema = z.object({
	role: z.string(),
	content: z.string(),
	timestamp: z.string(),
});

export const ContentStoreRecordSchema = z.object({
	slug: z.string(),
	content_type: z.enum([
		"weekly",
		"thematic",
		"reading_list",
		"digest",
		"daily_social",
		"seed",
		"journal",
	]),
	title: z.string(),
	body: z.string().default(""),
	status: z.enum(["draft", "review", "ready", "published", "archived"]).default("draft"),
	created_at: z.string(),
	source_dates: z.array(z.string()).default([]),
	tags: z.array(z.string()).default([]),
	images: z.array(ContentStoreImageSchema).default([]),
	platforms: z.record(z.string(), ContentStorePlatformSchema).default({}),
	chat_history: z.array(ContentStoreChatMessageSchema).default([]),
	metadata: z.record(z.string(), z.unknown()).default({}),
	file_path: z.string().default(""),
});

export const ContentStoreDataSchema = z.record(z.string(), ContentStoreRecordSchema);

export type ContentStoreImage = z.infer<typeof ContentStoreImageSchema>;
export type ContentStorePlatform = z.infer<typeof ContentStorePlatformSchema>;
export type ContentStoreChatMessage = z.infer<typeof ContentStoreChatMessageSchema>;
export type ContentStoreRecord = z.infer<typeof ContentStoreRecordSchema>;
export type ContentStoreData = z.infer<typeof ContentStoreDataSchema>;

// --- Studio / Review Queue ---

export const ChatMessageSchema = z.object({
	role: z.enum(["user", "assistant"]),
	content: z.string(),
	timestamp: z.string(),
});

export const PlatformContentSchema = z.object({
	enabled: z.boolean().default(true),
	content: z.string().nullable().default(null),
	published: z.boolean().default(false),
	postiz_id: z.string().nullable().default(null),
});

export const ReviewItemSchema = z.object({
	slug: z.string(),
	title: z.string(),
	type: z.enum(["weekly", "thematic", "daily-social", "intake"]),
	status: z.enum(["draft", "ready", "published"]).default("draft"),
	generated_at: z.string(),
	source_content: z.string().default(""),
	platforms: z.record(z.string(), PlatformContentSchema).default({}),
	chat_history: z.array(ChatMessageSchema).default([]),
});

export const ReviewQueueSchema = z.object({
	items: z.array(ReviewItemSchema).default([]),
});

export const CreateStudioItemSchema = z.object({
	title: z.string().min(1),
	body: z.string().min(1),
	content_type: z
		.enum(["weekly", "thematic", "reading_list", "digest", "daily_social", "seed", "journal"])
		.default("journal"),
	source_date: z.string().optional(),
	tags: z.array(z.string()).default([]),
});

export type CreateStudioItem = z.infer<typeof CreateStudioItemSchema>;

export const StudioPublishRequestSchema = z.object({
	platforms: z.array(z.string()).min(1),
	mode: z.enum(["draft", "schedule", "now"]).default("draft"),
	scheduled_at: z.string().optional(),
});

// --- Ghost Publishing ---

export const GhostPublishRequestSchema = z.object({
	target: z.string().min(1),
	status: z.enum(["draft", "published"]).default("draft"),
	tags: z.array(z.string()).default([]),
});

export const GhostTargetSchema = z.object({
	name: z.string(),
	label: z.string(),
	configured: z.boolean(),
});

export const BatchImageRequestSchema = z.object({
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
		.default("reflective"),
});

/** Schema for the AI SDK chat request body sent by TextStreamChatTransport.
 *  Messages use the AI SDK wire format (parts-based), so we passthrough and
 *  only validate the fields we extract in the endpoint. */
export const StudioChatRequestSchema = z.object({
	messages: z.array(z.record(z.unknown())),
	content: z.string(),
	platform: z.string().min(1),
	slug: z.string().optional(),
});

export type StudioChatRequest = z.infer<typeof StudioChatRequestSchema>;
export type ChatMessage = z.infer<typeof ChatMessageSchema>;
export type PlatformContent = z.infer<typeof PlatformContentSchema>;
export type ReviewItem = z.infer<typeof ReviewItemSchema>;
export type ReviewQueue = z.infer<typeof ReviewQueueSchema>;
export type StudioPublishRequest = z.infer<typeof StudioPublishRequestSchema>;
export type GhostPublishRequest = z.infer<typeof GhostPublishRequestSchema>;
export type GhostTarget = z.infer<typeof GhostTargetSchema>;
export type BatchImageRequest = z.infer<typeof BatchImageRequestSchema>;
