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

/**
 * Split thread content into separate tweet entries.
 * Supports `---` delimiters (preferred) or numbered tweets (`1/ ...`, `2/ ...`).
 */
export function splitThread(content: string): Array<{ content: string; image: unknown[] }> {
  const stripped = content.trim();

  // Primary: split on --- delimiter lines
  if (/^\s*---\s*$/m.test(stripped)) {
    const parts = stripped.split(/\n\s*---\s*\n/);
    const tweets = parts.map((p) => p.trim()).filter(Boolean);
    if (tweets.length > 1) {
      return tweets.map((t) => ({ content: t, image: [] }));
    }
  }

  // Fallback: numbered tweets (1/ ... 2/ ...)
  const parts = stripped.split(/\n*(?=\d+[/)]\s)/);
  const tweets = parts
    .map((p) => p.replace(/^\d+[/)]\s*/, "").trim())
    .filter(Boolean);
  if (tweets.length > 1) {
    return tweets.map((t) => ({ content: t, image: [] }));
  }

  // Single post
  return [{ content: stripped, image: [] }];
}

export async function createPost(
  content: string,
  integrationIds: string[],
  options: {
    postType?: string;
    scheduledAt?: string;
    imageUrl?: string;
    provider?: string;
  } = {},
): Promise<unknown> {
  const imageArray = options.imageUrl ? [{ url: options.imageUrl }] : [];
  const provider = options.provider ?? "";

  const posts = integrationIds.map((id) => {
    const settings: Record<string, string> = { __type: provider };
    if (provider === "x") {
      settings["who_can_reply_post"] = "everyone";
    }

    const value =
      provider === "x" ? splitThread(content) : [{ content, image: imageArray }];

    if (provider === "x" && value.length > 0 && imageArray.length > 0) {
      value[0]!.image = imageArray;
    }

    return { integration: { id }, value, settings };
  });

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
