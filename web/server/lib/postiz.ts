/**
 * Postiz API proxy client — keeps API key server-side.
 */
import { getConfig } from "./config.js";

interface PostizRequestOptions {
	method: string;
	path: string;
	body?: unknown;
}

export class PostizProxyError extends Error {
	constructor(
		public status: number,
		message: string,
	) {
		super(message);
		this.name = "PostizProxyError";
	}
}

async function postizRequest({ method, path, body }: PostizRequestOptions): Promise<unknown> {
	const config = getConfig();
	if (!config.POSTIZ_URL || !config.POSTIZ_API_KEY) {
		throw new PostizProxyError(503, "Postiz not configured");
	}

	const url = `${config.POSTIZ_URL.replace(/\/$/, "")}${path}`;
	const resp = await fetch(url, {
		method,
		headers: {
			Authorization: config.POSTIZ_API_KEY,
			"Content-Type": "application/json",
			Accept: "application/json",
		},
		body: body ? JSON.stringify(body) : undefined,
	});

	if (!resp.ok) {
		const text = await resp.text().catch(() => "");
		throw new PostizProxyError(resp.status, `Postiz API error: ${resp.status} ${text}`);
	}

	const text = await resp.text();
	return text ? JSON.parse(text) : {};
}

export async function listIntegrations(): Promise<
	Array<{ id: string; name: string; provider: string; identifier: string }>
> {
	const data = await postizRequest({ method: "GET", path: "/integrations" });
	interface PostizIntegrationItem {
		id: string;
		name: string;
		provider: string;
		providerIdentifier?: string;
		identifier: string;
	}
	const record = data as { integrations?: PostizIntegrationItem[] };
	const items: PostizIntegrationItem[] = Array.isArray(data) ? data : (record.integrations ?? []);
	return items.map((item) => ({
		id: item.id ?? "",
		name: item.name ?? "",
		provider: item.providerIdentifier ?? item.provider ?? item.identifier ?? "",
		identifier: item.identifier ?? "",
	}));
}

export async function createPost(
	content: string,
	integrationIds: string[],
	options: { postType?: string; scheduledAt?: string; imageUrl?: string } = {},
): Promise<unknown> {
	const imageArray = options.imageUrl ? [{ url: options.imageUrl }] : [];
	const posts = integrationIds.map((id) => ({
		integration: { id },
		value: [{ content, image: imageArray }],
		settings: { __type: "" },
	}));

	return postizRequest({
		method: "POST",
		path: "/posts",
		body: {
			type: options.postType ?? "draft",
			shortLink: false,
			tags: [],
			date: options.scheduledAt ?? new Date().toISOString(),
			posts,
		},
	});
}

export function isPostizConfigured(): boolean {
	const config = getConfig();
	return Boolean(config.POSTIZ_URL && config.POSTIZ_API_KEY);
}
