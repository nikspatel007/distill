/**
 * ContentStore — load and persist the .distill-content-store.json file.
 *
 * The ContentStore is the primary source of truth for publishable content.
 * It is a dict keyed by slug, with each record holding title, body, status,
 * per-platform adapted content, chat history, and image metadata.
 */
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { getConfig } from "./config.js";

const STORE_FILENAME = ".distill-content-store.json";

export interface ContentStoreImage {
	filename: string;
	role: string;
	prompt: string;
	relative_path: string;
}

export interface ContentStorePlatform {
	platform: string;
	content: string;
	published: boolean;
	published_at: string | null;
	external_id: string;
}

export interface ContentStoreChatMessage {
	role: string;
	content: string;
	timestamp: string;
}

export interface ContentStoreRecord {
	slug: string;
	content_type:
		| "weekly"
		| "thematic"
		| "reading_list"
		| "digest"
		| "daily_social"
		| "seed"
		| "journal";
	title: string;
	body: string;
	status: "draft" | "review" | "ready" | "published" | "archived";
	created_at: string;
	source_dates: string[];
	tags: string[];
	images: ContentStoreImage[];
	platforms: Record<string, ContentStorePlatform>;
	chat_history: ContentStoreChatMessage[];
	metadata: Record<string, unknown>;
	file_path: string;
}

export type ContentStoreData = Record<string, ContentStoreRecord>;

function storePath(): string {
	const config = getConfig();
	return join(config.OUTPUT_DIR, STORE_FILENAME);
}

export function loadContentStore(): ContentStoreData {
	const path = storePath();
	if (!existsSync(path)) return {};
	try {
		const raw = JSON.parse(readFileSync(path, "utf-8"));
		// Python ContentStore writes {"records": [...]} format.
		// Convert to slug-keyed dict for TS consumption.
		if (raw.records && Array.isArray(raw.records)) {
			const data: ContentStoreData = {};
			for (const record of raw.records) {
				if (record.slug) data[record.slug] = record;
			}
			return data;
		}
		// Already in slug-keyed dict format
		return raw as ContentStoreData;
	} catch {
		return {};
	}
}

export function saveContentStore(data: ContentStoreData): void {
	const path = storePath();
	// Write in Python-compatible {"records": [...]} format
	const records = Object.values(data);
	writeFileSync(path, JSON.stringify({ records }, null, 2));
}

export function getContentRecord(slug: string): ContentStoreRecord | null {
	const store = loadContentStore();
	return store[slug] ?? null;
}

export function updateContentRecord(
	slug: string,
	updates: Partial<ContentStoreRecord>,
): ContentStoreRecord | null {
	const store = loadContentStore();
	const record = store[slug];
	if (!record) return null;
	Object.assign(record, updates);
	saveContentStore(store);
	return record;
}

export function deleteContentRecord(slug: string): boolean {
	const store = loadContentStore();
	if (!store[slug]) return false;
	delete store[slug];
	saveContentStore(store);
	return true;
}
