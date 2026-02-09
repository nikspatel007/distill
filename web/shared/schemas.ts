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
	created: z.string().optional(),
});

// --- Intake Frontmatter ---

export const IntakeFrontmatterSchema = z.object({
	date: z.string().optional(),
	type: z.string().default("intake"),
	sources: z.array(z.string()).default([]),
	item_count: z.number().default(0),
	tags: z.array(z.string()).default([]),
	created: z.string().optional(),
});

// --- API Response types ---

export const DashboardResponseSchema = z.object({
	journalCount: z.number(),
	blogCount: z.number(),
	intakeCount: z.number(),
	pendingPublish: z.number(),
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
	filename: z.string(),
	platformsPublished: z.array(z.string()),
});

export const BlogDetailSchema = z.object({
	meta: BlogPostSchema,
	content: z.string(),
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
