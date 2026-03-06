import RSSParser from "rss-parser";

const parser = new RSSParser();

export interface RSSItem {
  title: string;
  url: string;
  summary: string;
  author: string;
  siteName: string;
  publishedAt: string;
  tags: string[];
}

export async function fetchFeed(feedUrl: string): Promise<RSSItem[]> {
  try {
    const feed = await parser.parseURL(feedUrl);
    return (feed.items ?? []).slice(0, 10).map((item) => ({
      title: item.title ?? "Untitled",
      url: item.link ?? "",
      summary: (item.contentSnippet ?? item.content ?? "").slice(0, 500),
      author: item.creator ?? item.author ?? "",
      siteName: feed.title ?? new URL(feedUrl).hostname,
      publishedAt: item.isoDate ?? item.pubDate ?? new Date().toISOString(),
      tags: (item.categories ?? []).slice(0, 5),
    }));
  } catch (error) {
    console.warn(`Failed to fetch RSS feed ${feedUrl}:`, error);
    return [];
  }
}

export async function fetchFeeds(feedUrls: string[]): Promise<RSSItem[]> {
  const results = await Promise.allSettled(
    feedUrls.map((url) => fetchFeed(url))
  );
  const items: RSSItem[] = [];
  for (const result of results) {
    if (result.status === "fulfilled") {
      items.push(...result.value);
    }
  }
  // Deduplicate by URL
  const seen = new Set<string>();
  return items.filter((item) => {
    if (!item.url || seen.has(item.url)) return false;
    seen.add(item.url);
    return true;
  });
}
