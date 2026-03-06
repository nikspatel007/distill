import { z } from "zod";

export const FeedItemSchema = z.object({
  id: z.number(),
  userId: z.string().uuid(),
  displayName: z.string(),
  avatarUrl: z.string().nullable().default(null),
  type: z.enum(["highlight", "share", "draft_published"]),
  title: z.string(),
  summary: z.string().nullable().default(null),
  url: z.string().nullable().default(null),
  imageUrl: z.string().nullable().default(null),
  metadata: z.record(z.unknown()).default({}),
  createdAt: z.string(),
});

export const FollowSchema = z.object({
  followerId: z.string().uuid(),
  followingId: z.string().uuid(),
  createdAt: z.string(),
});

export const FollowUserSchema = z.object({
  userId: z.string().uuid(),
});

export const UserCardSchema = z.object({
  id: z.string().uuid(),
  displayName: z.string(),
  avatarUrl: z.string().nullable().default(null),
  isFollowing: z.boolean().default(false),
});

export type FeedItem = z.infer<typeof FeedItemSchema>;
export type Follow = z.infer<typeof FollowSchema>;
export type FollowUser = z.infer<typeof FollowUserSchema>;
export type UserCard = z.infer<typeof UserCardSchema>;
