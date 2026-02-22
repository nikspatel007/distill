/**
 * Image generation tool — wraps server/lib/images.ts.
 */
import { getConfig } from "../lib/config.js";
import { loadContentStore, saveContentStore } from "../lib/content-store.js";
import { generateImage as generate } from "../lib/images.js";

export { isImageConfigured } from "../lib/images.js";

export async function generateImage(params: {
	prompt: string;
	mood: string;
	slug?: string;
}): Promise<{ url?: string; alt?: string; mood?: string; error?: string }> {
	const config = getConfig();
	const imageResult = await generate(params.prompt, {
		outputDir: config.OUTPUT_DIR,
		mood: params.mood,
		slug: params.slug ?? "studio",
	});

	if (!imageResult) {
		return { error: "Image generation not available or failed" };
	}

	// Save to ContentStore if slug provided
	if (params.slug) {
		const store = loadContentStore();
		const record = store[params.slug];
		if (record) {
			record.images.push({
				filename: imageResult.filename,
				role: "hero",
				prompt: params.prompt,
				relative_path: imageResult.relativePath,
			});
			saveContentStore(store);
		}
	}

	return {
		url: `/api/studio/images/${imageResult.relativePath}`,
		alt: params.prompt,
		mood: params.mood,
	};
}
