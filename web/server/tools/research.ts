import * as cheerio from "cheerio";
import { loadContentStore, saveContentStore } from "../lib/content-store.js";

/**
 * Extract readable text from HTML.
 * Removes script, style, nav, header, footer, aside elements.
 * Prefers <article> or <main> content if > 100 chars.
 */
export function extractReadableText(html: string): string {
	const $ = cheerio.load(html);

	// Remove unwanted elements
	$("script, style, nav, header, footer, aside").remove();

	// Try to extract from article or main first
	const article = $("article").text().trim();
	if (article.length > 100) {
		return article;
	}

	const main = $("main").text().trim();
	if (main.length > 100) {
		return main;
	}

	// Fall back to body
	return $("body").text().trim() || $.text().trim();
}

/**
 * Fetch URL and extract readable content.
 * Returns { title, text, url, error? }
 */
export async function fetchUrl(params: {
	url: string;
}): Promise<{ title: string; text: string; url: string; error?: string }> {
	try {
		const response = await fetch(params.url, {
			headers: {
				"User-Agent": "Distill/1.0 (content research tool)",
				Accept: "text/html, application/json, text/plain",
			},
		});

		if (!response.ok) {
			return {
				title: "",
				text: "",
				url: params.url,
				error: `HTTP ${response.status}: ${response.statusText}`,
			};
		}

		const contentType = response.headers.get("content-type") || "";
		const body = await response.text();

		let title = "";
		let text = "";

		if (contentType.includes("text/html")) {
			const $ = cheerio.load(body);
			title = $("title").text().trim() || $("h1").first().text().trim();
			text = extractReadableText(body);
		} else {
			// Plain text or JSON
			text = body;
			title = params.url.split("/").pop() || params.url;
		}

		// Truncate to 50000 chars
		if (text.length > 50000) {
			text = text.substring(0, 50000);
		}

		return { title, text, url: params.url };
	} catch (err) {
		return {
			title: "",
			text: "",
			url: params.url,
			error: err instanceof Error ? err.message : String(err),
		};
	}
}

/**
 * Fetch URL and save to ContentStore as draft digest.
 * Returns { saved: boolean, slug: string, title: string, error? }
 */
export async function saveToIntake(params: {
	url: string;
	tags?: string[];
	notes?: string;
}): Promise<{ saved: boolean; slug: string; title: string; error?: string }> {
	// Fetch the URL first
	const fetchResult = await fetchUrl({ url: params.url });

	if (fetchResult.error) {
		return {
			saved: false,
			slug: "",
			title: "",
			error: fetchResult.error,
		};
	}

	// Generate slug from title
	const baseSlug = fetchResult.title
		.toLowerCase()
		.replace(/[^a-z0-9]+/g, "-")
		.replace(/^-|-$/g, "")
		.substring(0, 100);

	// Load content store and deduplicate slug
	const store = loadContentStore();
	let slug = baseSlug;
	let counter = 1;

	while (slug in store) {
		slug = `${baseSlug}-${counter}`;
		counter++;
	}

	// Prepare body with optional notes
	let body = fetchResult.text;
	if (params.notes) {
		body = `${params.notes}\n\n---\n\n${body}`;
	}

	// Create content store record
	store[slug] = {
		slug,
		title: fetchResult.title,
		body,
		content_type: "digest",
		status: "draft",
		created_at: new Date().toISOString(),
		source_dates: [],
		tags: params.tags || ["research"],
		images: [],
		platforms: {},
		chat_history: [],
		metadata: {
			source_url: params.url,
		},
		file_path: "",
	};

	// Save content store
	saveContentStore(store);

	return {
		saved: true,
		slug,
		title: fetchResult.title,
	};
}
