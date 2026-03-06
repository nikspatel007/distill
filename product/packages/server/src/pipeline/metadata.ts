export interface UrlMetadata {
  title: string;
  description: string;
  author: string;
  siteName: string;
}

export async function extractMetadata(url: string): Promise<UrlMetadata> {
  try {
    const response = await fetch(url, {
      headers: { "User-Agent": "Distill/1.0 (https://distill.dev)" },
      signal: AbortSignal.timeout(10000),
    });
    const html = await response.text();

    const getMetaContent = (name: string): string => {
      const patterns = [
        new RegExp(
          `<meta[^>]*(?:name|property)=["']${name}["'][^>]*content=["']([^"']*)["']`,
          "i",
        ),
        new RegExp(
          `<meta[^>]*content=["']([^"']*)["'][^>]*(?:name|property)=["']${name}["']`,
          "i",
        ),
      ];
      for (const pattern of patterns) {
        const match = html.match(pattern);
        if (match?.[1]) return match[1];
      }
      return "";
    };

    const titleMatch = html.match(/<title[^>]*>([^<]*)<\/title>/i);

    return {
      title: getMetaContent("og:title") || titleMatch?.[1]?.trim() || "",
      description:
        getMetaContent("og:description") || getMetaContent("description") || "",
      author:
        getMetaContent("author") || getMetaContent("article:author") || "",
      siteName: getMetaContent("og:site_name") || new URL(url).hostname,
    };
  } catch {
    return {
      title: "",
      description: "",
      author: "",
      siteName: new URL(url).hostname,
    };
  }
}
