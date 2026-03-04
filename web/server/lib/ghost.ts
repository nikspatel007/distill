/**
 * Ghost CMS client — JWT auth, mobiledoc post creation, image upload.
 *
 * Ported from src/integrations/ghost.py. Uses Bun's built-in crypto
 * (Web Crypto API) for JWT generation — no extra dependencies.
 */
import { getConfig } from "./config.js";

// ---------------------------------------------------------------------------
// JWT generation (HS256, Ghost Admin API)
// ---------------------------------------------------------------------------

function base64UrlEncode(data: Uint8Array | string): string {
	const raw = typeof data === "string" ? data : Buffer.from(data).toString("base64");
	return raw.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

/**
 * Build a Ghost Admin API JWT using HS256.
 * The Admin API key format is `{key_id}:{hex_secret}`.
 */
export async function generateGhostJWT(adminApiKey: string): Promise<string> {
	const [keyId, hexSecret] = adminApiKey.split(":");
	if (!keyId || !hexSecret) {
		throw new Error("Invalid Ghost Admin API key format (expected id:hexsecret)");
	}

	const hexPairs = hexSecret.match(/.{1,2}/g) ?? [];
	const secret = new Uint8Array(hexPairs.map((b) => Number.parseInt(b, 16)));

	const header = base64UrlEncode(
		Buffer.from(JSON.stringify({ alg: "HS256", typ: "JWT", kid: keyId })).toString("base64"),
	);

	const now = Math.floor(Date.now() / 1000);
	const payload = base64UrlEncode(
		Buffer.from(
			JSON.stringify({
				iat: now,
				exp: now + 5 * 60,
				aud: "/admin/",
			}),
		).toString("base64"),
	);

	const signingInput = `${header}.${payload}`;
	const key = await crypto.subtle.importKey(
		"raw",
		secret,
		{ name: "HMAC", hash: "SHA-256" },
		false,
		["sign"],
	);
	const signature = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(signingInput));
	const sig = base64UrlEncode(new Uint8Array(signature));

	return `${header}.${payload}.${sig}`;
}

// ---------------------------------------------------------------------------
// Mobiledoc formatting
// ---------------------------------------------------------------------------

/**
 * Wrap markdown content in Ghost's mobiledoc JSON format.
 */
export function markdownToMobiledoc(markdown: string): string {
	const mobiledoc = {
		version: "0.3.1",
		ghostVersion: "4.0",
		markups: [],
		atoms: [],
		cards: [["markdown", { markdown }]],
		sections: [[10, 0]],
	};
	return JSON.stringify(mobiledoc);
}

// ---------------------------------------------------------------------------
// Ghost API client
// ---------------------------------------------------------------------------

export interface GhostPostOptions {
	status?: "draft" | "published";
	tags?: string[];
	featureImage?: string;
}

export interface GhostPostResult {
	id: string;
	url: string;
	title: string;
	status: string;
}

export class GhostClient {
	private baseUrl: string;
	private adminApiKey: string;

	constructor(url: string, adminApiKey: string) {
		this.baseUrl = url.replace(/\/$/, "");
		this.adminApiKey = adminApiKey;
	}

	private async request(method: string, path: string, data?: unknown): Promise<unknown> {
		const url = `${this.baseUrl}/ghost/api/admin${path}`;
		const token = await generateGhostJWT(this.adminApiKey);

		const resp = await fetch(url, {
			method,
			headers: {
				Authorization: `Ghost ${token}`,
				"Content-Type": "application/json",
			},
			body: data ? JSON.stringify(data) : undefined,
		});

		if (!resp.ok) {
			const text = await resp.text().catch(() => "");
			throw new Error(`Ghost API error: ${resp.status} ${text}`);
		}

		return resp.json();
	}

	/**
	 * Create a post in Ghost CMS.
	 */
	async createPost(
		title: string,
		markdown: string,
		opts: GhostPostOptions = {},
	): Promise<GhostPostResult> {
		const postData: Record<string, unknown> = {
			title,
			mobiledoc: markdownToMobiledoc(markdown),
			status: opts.status ?? "draft",
		};
		if (opts.tags?.length) {
			// biome-ignore lint/complexity/useLiteralKeys: Record<string, unknown> requires bracket notation
			postData["tags"] = opts.tags.map((name) => ({ name }));
		}
		if (opts.featureImage) {
			// biome-ignore lint/complexity/useLiteralKeys: Record<string, unknown> requires bracket notation
			postData["feature_image"] = opts.featureImage;
		}

		const result = (await this.request("POST", "/posts/", { posts: [postData] })) as {
			posts: GhostPostResult[];
		};
		const post = result.posts[0];
		if (!post) throw new Error("Ghost API returned empty posts array");
		return post;
	}

	/**
	 * Upload an image to Ghost and return its URL.
	 */
	async uploadImage(filePath: string): Promise<string | null> {
		try {
			const token = await generateGhostJWT(this.adminApiKey);
			const url = `${this.baseUrl}/ghost/api/admin/images/upload/`;

			const file = Bun.file(filePath);
			if (!(await file.exists())) return null;

			const fileData = await file.arrayBuffer();
			const filename = filePath.split("/").pop() ?? "image.png";
			const ext = filename.split(".").pop()?.toLowerCase();
			const contentType = ext === "png" ? "image/png" : "image/jpeg";

			const boundary = "----DistillUploadBoundary";
			const parts: Uint8Array[] = [];
			const encoder = new TextEncoder();

			parts.push(encoder.encode(`--${boundary}\r\n`));
			parts.push(
				encoder.encode(`Content-Disposition: form-data; name="file"; filename="${filename}"\r\n`),
			);
			parts.push(encoder.encode(`Content-Type: ${contentType}\r\n\r\n`));
			parts.push(new Uint8Array(fileData));
			parts.push(encoder.encode(`\r\n--${boundary}--\r\n`));

			const body = Buffer.concat(parts);

			const resp = await fetch(url, {
				method: "POST",
				headers: {
					Authorization: `Ghost ${token}`,
					"Content-Type": `multipart/form-data; boundary=${boundary}`,
				},
				body,
			});

			if (!resp.ok) return null;

			const data = (await resp.json()) as { images: Array<{ url: string }> };
			return data.images[0]?.url ?? null;
		} catch {
			return null;
		}
	}
}

// ---------------------------------------------------------------------------
// Config helpers — system-driven Ghost target discovery
// ---------------------------------------------------------------------------

export interface GhostTarget {
	name: string;
	label: string;
	configured: boolean;
	url: string;
	apiKey: string;
}

/** Cache for Ghost site titles fetched from the API. */
const _siteTitleCache = new Map<string, string>();

/**
 * Fetch the Ghost site title from the admin API.
 * Caches results to avoid repeated API calls.
 */
async function fetchSiteTitle(url: string, apiKey: string): Promise<string | null> {
	const cacheKey = url;
	const cached = _siteTitleCache.get(cacheKey);
	if (cached) return cached;

	try {
		const token = await generateGhostJWT(apiKey);
		const resp = await fetch(`${url.replace(/\/$/, "")}/ghost/api/admin/site/`, {
			headers: { Authorization: `Ghost ${token}` },
		});
		if (!resp.ok) return null;
		const data = (await resp.json()) as { site?: { title?: string } };
		const title = data.site?.title ?? null;
		if (title) _siteTitleCache.set(cacheKey, title);
		return title;
	} catch {
		return null;
	}
}

/** Extract a readable label from a Ghost URL (hostname without common prefixes). */
function labelFromUrl(url: string): string {
	try {
		const hostname = new URL(url).hostname;
		// Strip common subdomains/suffixes for a cleaner label
		return hostname
			.replace(/\.ghost\.io$/, "")
			.replace(/\.ondigitalocean\.app$/, "")
			.replace(/^ghost-/, "")
			.replace(/-/g, " ")
			.replace(/\b\w/g, (c) => c.toUpperCase());
	} catch {
		return url;
	}
}

/**
 * Check if a specific Ghost target is configured.
 */
export function isGhostConfigured(target: string): boolean {
	const targets = getGhostTargets();
	return targets.some((t) => t.name === target && t.configured);
}

/**
 * Get all Ghost targets from environment configuration.
 * Only returns targets that have both URL and API key set.
 * Labels are derived from: GHOST_LABEL env var > URL hostname.
 * Call resolveGhostLabels() once at startup to fetch site titles from the API.
 */
export function getGhostTargets(): GhostTarget[] {
	const config = getConfig();
	const targets: GhostTarget[] = [];

	// Primary Ghost instance
	if (config.GHOST_URL || config.GHOST_ADMIN_API_KEY) {
		const configured = Boolean(config.GHOST_URL && config.GHOST_ADMIN_API_KEY);
		const label =
			config.GHOST_LABEL ||
			_siteTitleCache.get(config.GHOST_URL) ||
			(config.GHOST_URL ? labelFromUrl(config.GHOST_URL) : "Ghost");
		targets.push({
			name: "primary",
			label,
			configured,
			url: config.GHOST_URL,
			apiKey: config.GHOST_ADMIN_API_KEY,
		});
	}

	// Personal Ghost instance
	if (config.GHOST_PERSONAL_URL || config.GHOST_PERSONAL_ADMIN_API_KEY) {
		const configured = Boolean(config.GHOST_PERSONAL_URL && config.GHOST_PERSONAL_ADMIN_API_KEY);
		const label =
			config.GHOST_PERSONAL_LABEL ||
			_siteTitleCache.get(config.GHOST_PERSONAL_URL) ||
			(config.GHOST_PERSONAL_URL ? labelFromUrl(config.GHOST_PERSONAL_URL) : "Ghost Personal");
		targets.push({
			name: "personal",
			label,
			configured,
			url: config.GHOST_PERSONAL_URL,
			apiKey: config.GHOST_PERSONAL_ADMIN_API_KEY,
		});
	}

	return targets;
}

/**
 * Resolve Ghost site titles from the API and cache them.
 * Call once at server startup for best UX.
 */
export async function resolveGhostLabels(): Promise<void> {
	const config = getConfig();
	const tasks: Promise<void>[] = [];

	if (config.GHOST_URL && config.GHOST_ADMIN_API_KEY && !config.GHOST_LABEL) {
		tasks.push(
			fetchSiteTitle(config.GHOST_URL, config.GHOST_ADMIN_API_KEY).then((title) => {
				if (title) _siteTitleCache.set(config.GHOST_URL, title);
			}),
		);
	}
	if (
		config.GHOST_PERSONAL_URL &&
		config.GHOST_PERSONAL_ADMIN_API_KEY &&
		!config.GHOST_PERSONAL_LABEL
	) {
		tasks.push(
			fetchSiteTitle(config.GHOST_PERSONAL_URL, config.GHOST_PERSONAL_ADMIN_API_KEY).then(
				(title) => {
					if (title) _siteTitleCache.set(config.GHOST_PERSONAL_URL, title);
				},
			),
		);
	}

	await Promise.allSettled(tasks);
}

/**
 * Create a GhostClient for a specific target by name.
 */
export function createGhostClient(targetName: string): GhostClient | null {
	const target = getGhostTargets().find((t) => t.name === targetName && t.configured);
	if (!target) return null;
	return new GhostClient(target.url, target.apiKey);
}
