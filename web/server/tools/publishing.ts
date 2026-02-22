/**
 * Publishing tools — ContentStore → Postiz integration.
 */
import { getConfig } from "../lib/config.js";
import { getContentRecord, loadContentStore, saveContentStore } from "../lib/content-store.js";
import { createPost, isPostizConfigured, listIntegrations } from "../lib/postiz.js";

const PLATFORM_PROVIDER_MAP: Record<string, string> = {
	x: "x",
	linkedin: "linkedin",
	slack: "slack",
};

export async function listPostizIntegrations(): Promise<{
	configured: boolean;
	integrations: Array<{ id: string; name: string; provider: string }>;
}> {
	if (!isPostizConfigured()) {
		return { configured: false, integrations: [] };
	}

	try {
		const integrations = await listIntegrations();
		return { configured: true, integrations };
	} catch (error) {
		console.error("Failed to list Postiz integrations:", error);
		return { configured: true, integrations: [] };
	}
}

export async function publishContent(params: {
	slug: string;
	platforms: string[];
	mode: string;
	scheduled_at?: string;
}): Promise<{
	results: Array<{ platform: string; success: boolean; error?: string }>;
	error?: string;
}> {
	if (!isPostizConfigured()) {
		return { results: [], error: "Postiz not configured" };
	}

	const record = getContentRecord(params.slug);
	if (!record) {
		return { results: [], error: "Content record not found" };
	}

	const integrations = await listIntegrations().catch(
		() => [] as Array<{ id: string; name: string; provider: string; identifier: string }>,
	);

	const results: Array<{ platform: string; success: boolean; error?: string }> = [];

	for (const platform of params.platforms) {
		const platformRecord = record.platforms[platform];
		if (!platformRecord?.content) {
			results.push({
				platform,
				success: false,
				error: "No adapted content for platform",
			});
			continue;
		}

		if (platformRecord.published) {
			results.push({
				platform,
				success: false,
				error: "Already published",
			});
			continue;
		}

		const providerName = PLATFORM_PROVIDER_MAP[platform];
		if (!providerName) {
			results.push({
				platform,
				success: false,
				error: "Unknown platform provider mapping",
			});
			continue;
		}

		const integration = integrations.find((i) => i.provider === providerName);
		if (!integration) {
			results.push({
				platform,
				success: false,
				error: `No Postiz integration found for provider: ${providerName}`,
			});
			continue;
		}

		try {
			await createPost(platformRecord.content, [integration.id], {
				postType: params.mode,
				scheduledAt: params.scheduled_at,
			});

			// Mark as published in ContentStore
			const store = loadContentStore();
			const rec = store[params.slug];
			const platformRec = rec?.platforms[platform];
			if (rec && platformRec) {
				platformRec.published = true;
				platformRec.published_at = new Date().toISOString();
				saveContentStore(store);
			}

			results.push({ platform, success: true });
		} catch (error) {
			results.push({
				platform,
				success: false,
				error: error instanceof Error ? error.message : "Unknown error",
			});
		}
	}

	return { results };
}

export async function listPostizPosts(params: {
	status?: string;
	limit?: number;
}): Promise<{ posts: unknown[]; error?: string }> {
	if (!isPostizConfigured()) {
		return { posts: [], error: "Postiz not configured" };
	}

	try {
		const config = getConfig();
		const url = new URL("/posts", config.POSTIZ_URL);
		if (params.status) {
			url.searchParams.set("status", params.status);
		}
		if (params.limit) {
			url.searchParams.set("limit", params.limit.toString());
		}

		const resp = await fetch(url.toString(), {
			method: "GET",
			headers: {
				Authorization: config.POSTIZ_API_KEY,
				"Content-Type": "application/json",
				Accept: "application/json",
			},
		});

		if (!resp.ok) {
			return { posts: [], error: `Postiz API error: ${resp.status}` };
		}

		const text = await resp.text();
		const data = text ? JSON.parse(text) : [];
		const posts = Array.isArray(data) ? data : [];

		return { posts };
	} catch (error) {
		return {
			posts: [],
			error: error instanceof Error ? error.message : "Unknown error",
		};
	}
}
