/**
 * Content Store tools — pure async functions for ContentStore operations.
 * All functions return JSON-serializable objects for LLM/agent consumption.
 */
import {
	type ContentStoreRecord,
	deleteContentRecord,
	getContentRecord,
	loadContentStore,
	saveContentStore,
	updateContentRecord,
} from "../lib/content-store.js";

/**
 * List all content items with optional filtering.
 */
export async function listContent(params: {
	type?: string;
	status?: string;
}): Promise<{
	items: Array<{
		slug: string;
		title: string;
		type: string;
		status: string;
		created_at: string;
	}>;
}> {
	const store = loadContentStore();
	const allItems = Object.values(store);

	const filtered = allItems.filter((item) => {
		if (params.type && item.content_type !== params.type) return false;
		if (params.status && item.status !== params.status) return false;
		return true;
	});

	const items = filtered.map((item) => ({
		slug: item.slug,
		title: item.title,
		type: item.content_type,
		status: item.status,
		created_at: item.created_at,
	}));

	return { items };
}

/**
 * Get full content record by slug.
 */
export async function getContent(params: {
	slug: string;
}): Promise<ContentStoreRecord | { error: string }> {
	const record = getContentRecord(params.slug);
	if (!record) {
		return { error: "Content not found" };
	}
	return record;
}

/**
 * Update source content (body and optionally title).
 */
export async function updateSource(params: {
	slug: string;
	content: string;
	title?: string;
}): Promise<{ saved: boolean; error?: string }> {
	const updates: Partial<ContentStoreRecord> = {
		body: params.content,
	};
	if (params.title) {
		updates.title = params.title;
	}

	const result = updateContentRecord(params.slug, updates);
	if (!result) {
		return { saved: false, error: "Content not found" };
	}

	return { saved: true };
}

/**
 * Save platform-specific adapted content.
 */
export async function savePlatform(params: {
	slug: string;
	platform: string;
	content: string;
}): Promise<{ saved: boolean; platform: string; error?: string }> {
	const record = getContentRecord(params.slug);
	if (!record) {
		return { saved: false, platform: params.platform, error: "Content not found" };
	}

	const platforms = record.platforms ?? {};
	platforms[params.platform] = {
		platform: params.platform,
		content: params.content,
		published: false,
		published_at: null,
		external_id: "",
	};

	const result = updateContentRecord(params.slug, { platforms });
	if (!result) {
		return { saved: false, platform: params.platform, error: "Update failed" };
	}

	return { saved: true, platform: params.platform };
}

/**
 * Update content status.
 */
export async function updateStatus(params: {
	slug: string;
	status: string;
}): Promise<{ saved: boolean; error?: string }> {
	const validStatuses = ["draft", "review", "ready", "published", "archived"];
	if (!validStatuses.includes(params.status)) {
		return { saved: false, error: `Invalid status: ${params.status}` };
	}

	const result = updateContentRecord(params.slug, {
		status: params.status as ContentStoreRecord["status"],
	});
	if (!result) {
		return { saved: false, error: "Content not found" };
	}

	return { saved: true };
}

/**
 * Delete a content item by slug.
 */
export async function deleteContent(params: {
	slug: string;
}): Promise<{ deleted: boolean; error?: string }> {
	const result = deleteContentRecord(params.slug);
	if (!result) return { deleted: false, error: "Content not found" };
	return { deleted: true };
}

/**
 * Create new content item.
 */
export async function createContent(params: {
	title: string;
	body: string;
	content_type: string;
	tags?: string[];
}): Promise<{ slug: string; created: boolean }> {
	// Generate slug from title
	const baseSlug = params.title
		.toLowerCase()
		.replace(/[^a-z0-9]+/g, "-")
		.replace(/^-+|-+$/g, "")
		.slice(0, 60);

	// Ensure unique slug
	const store = loadContentStore();
	let slug = baseSlug;
	let counter = 1;
	while (store[slug]) {
		slug = `${baseSlug}-${counter}`;
		counter++;
	}

	const record: ContentStoreRecord = {
		slug,
		content_type: params.content_type as ContentStoreRecord["content_type"],
		title: params.title,
		body: params.body,
		status: "draft",
		created_at: new Date().toISOString(),
		source_dates: [],
		tags: params.tags ?? [],
		images: [],
		platforms: {},
		chat_history: [],
		metadata: {},
		file_path: "",
	};

	store[slug] = record;
	saveContentStore(store);

	return { slug, created: true };
}
