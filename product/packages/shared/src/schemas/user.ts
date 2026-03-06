import { z } from "zod";

export const UserProfileSchema = z.object({
  id: z.string().uuid(),
  displayName: z.string(),
  email: z.string().email().optional(),
  avatarUrl: z.string().url().nullable().default(null),
  createdAt: z.string(),
});

export const UserPreferencesSchema = z.object({
  timezone: z.string().default("America/New_York"),
  notificationsEnabled: z.boolean().default(true),
  sessionSharingEnabled: z.boolean().default(false),
  highlightSharingEnabled: z.boolean().default(true),
});

export const UpdateProfileSchema = z.object({
  displayName: z.string().min(1).optional(),
  avatarUrl: z.string().url().nullable().optional(),
  preferences: UserPreferencesSchema.partial().optional(),
});

export type UserProfile = z.infer<typeof UserProfileSchema>;
export type UserPreferences = z.infer<typeof UserPreferencesSchema>;
export type UpdateProfile = z.infer<typeof UpdateProfileSchema>;
