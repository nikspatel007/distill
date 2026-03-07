import {
  pgTable,
  uuid,
  text,
  serial,
  timestamp,
  date,
  jsonb,
  boolean,
  integer,
  uniqueIndex,
  primaryKey,
  index,
  vector,
} from "drizzle-orm/pg-core";

// --- Users (extends Supabase auth.users) ---

export const users = pgTable("users", {
  id: uuid("id").primaryKey(), // matches Supabase auth.users.id
  displayName: text("display_name").notNull(),
  avatarUrl: text("avatar_url"),
  preferences: jsonb("preferences").$type<{
    notificationsEnabled: boolean;
    shareSessions: boolean;
    shareHighlights: boolean;
  }>().default({
    notificationsEnabled: true,
    shareSessions: false,
    shareHighlights: true,
  }),
  createdAt: timestamp("created_at", { withTimezone: true }).defaultNow(),
});

// --- Shared URLs ---

export const sharedUrls = pgTable("shared_urls", {
  id: serial("id").primaryKey(),
  userId: uuid("user_id").references(() => users.id, { onDelete: "cascade" }).notNull(),
  url: text("url").notNull(),
  title: text("title"),
  note: text("note"),
  createdAt: timestamp("created_at", { withTimezone: true }).defaultNow().notNull(),
  processedAt: timestamp("processed_at", { withTimezone: true }),
}, (t) => [
  index("shared_urls_user_idx").on(t.userId),
]);

// --- Content Items ---

export const contentItems = pgTable("content_items", {
  id: serial("id").primaryKey(),
  userId: uuid("user_id").references(() => users.id, { onDelete: "cascade" }).notNull(),
  source: text("source").notNull(), // rss, manual, discovery, session, etc.
  url: text("url"),
  title: text("title").notNull(),
  summary: text("summary"),
  fullText: text("full_text"),
  tags: jsonb("tags").$type<string[]>().default([]),
  entities: jsonb("entities").$type<string[]>().default([]),
  publishedAt: timestamp("published_at", { withTimezone: true }),
  ingestedAt: timestamp("ingested_at", { withTimezone: true }).defaultNow().notNull(),
  imageUrl: text("image_url"),
  imagePrompt: text("image_prompt"),
  // embedding: vector("embedding", { dimensions: 1536 }), // uncomment when pgvector is ready
}, (t) => [
  index("content_items_user_idx").on(t.userId),
  index("content_items_user_date_idx").on(t.userId, t.ingestedAt),
  index("content_items_source_idx").on(t.source),
]);

// --- Reading Briefs ---

export const readingBriefs = pgTable("reading_briefs", {
  id: serial("id").primaryKey(),
  userId: uuid("user_id").references(() => users.id, { onDelete: "cascade" }).notNull(),
  date: date("date").notNull(),
  highlights: jsonb("highlights").$type<Array<{
    title: string;
    source: string;
    url: string;
    summary: string;
    tags: string[];
    imageUrl: string | null;
    imagePrompt: string | null;
  }>>().default([]),
  drafts: jsonb("drafts").$type<Array<{
    platform: string;
    content: string;
    charCount: number;
    sourceHighlights: string[];
    imageUrl: string | null;
  }>>().default([]),
  connection: jsonb("connection").$type<{
    today: string;
    past: string;
    connectionType: string;
    explanation: string;
    strength: number;
  } | null>().default(null),
  learningPulse: jsonb("learning_pulse").$type<Array<{
    topic: string;
    status: string;
    count: number;
    recentCount: number;
    firstSeen: string;
    lastSeen: string;
    sparkline: number[];
  }>>().default([]),
  discoveries: jsonb("discoveries").$type<Array<{
    title: string;
    url: string;
    source: string;
    summary: string;
    topic: string;
    contentType: string;
  }>>().default([]),
  createdAt: timestamp("created_at", { withTimezone: true }).defaultNow().notNull(),
}, (t) => [
  uniqueIndex("reading_briefs_user_date_idx").on(t.userId, t.date),
]);

// --- Follows ---

export const follows = pgTable("follows", {
  followerId: uuid("follower_id").references(() => users.id, { onDelete: "cascade" }).notNull(),
  followingId: uuid("following_id").references(() => users.id, { onDelete: "cascade" }).notNull(),
  createdAt: timestamp("created_at", { withTimezone: true }).defaultNow().notNull(),
}, (t) => [
  primaryKey({ columns: [t.followerId, t.followingId] }),
]);

// --- Feed Items ---

export const feedItems = pgTable("feed_items", {
  id: serial("id").primaryKey(),
  userId: uuid("user_id").references(() => users.id).notNull(),
  type: text("type").notNull(), // highlight, share, draft_published
  title: text("title").notNull(),
  summary: text("summary"),
  url: text("url"),
  imageUrl: text("image_url"),
  metadata: jsonb("metadata").$type<Record<string, unknown>>(),
  createdAt: timestamp("created_at", { withTimezone: true }).defaultNow(),
});

// --- Default Feeds (admin-curated RSS feeds) ---

export const defaultFeeds = pgTable("default_feeds", {
  id: serial("id").primaryKey(),
  url: text("url").notNull().unique(),
  name: text("name"),
  category: text("category"),
  active: boolean("active").default(true),
});

// --- Sessions (synced from user machines) ---

export const sessions = pgTable("sessions", {
  id: serial("id").primaryKey(),
  userId: uuid("user_id").references(() => users.id).notNull(),
  sessionId: text("session_id").notNull(), // original session UUID
  project: text("project").notNull(),
  summary: text("summary"),
  durationMinutes: integer("duration_minutes").notNull(),
  linesAdded: integer("lines_added").default(0),
  linesRemoved: integer("lines_removed").default(0),
  filesChanged: jsonb("files_changed").$type<string[]>().default([]),
  sessionTimestamp: timestamp("session_timestamp", { withTimezone: true }).notNull(),
  createdAt: timestamp("created_at", { withTimezone: true }).defaultNow(),
}, (t) => [
  uniqueIndex("sessions_user_session_idx").on(t.userId, t.sessionId),
]);
