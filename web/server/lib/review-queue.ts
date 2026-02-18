import { readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { type ReviewItem, type ReviewQueue, ReviewQueueSchema } from "../../shared/schemas.js";
import { getConfig } from "./config.js";

function queuePath(): string {
	return join(getConfig().OUTPUT_DIR, ".distill-review-queue.json");
}

export async function loadReviewQueue(): Promise<ReviewQueue> {
	try {
		const raw = await readFile(queuePath(), "utf-8");
		return ReviewQueueSchema.parse(JSON.parse(raw));
	} catch {
		return { items: [] };
	}
}

export async function saveReviewQueue(queue: ReviewQueue): Promise<void> {
	await writeFile(queuePath(), JSON.stringify(queue, null, 2), "utf-8");
}

export async function getReviewItem(slug: string): Promise<ReviewItem | null> {
	const queue = await loadReviewQueue();
	return queue.items.find((i) => i.slug === slug) ?? null;
}

export async function upsertReviewItem(item: ReviewItem): Promise<void> {
	const queue = await loadReviewQueue();
	const idx = queue.items.findIndex((i) => i.slug === item.slug);
	if (idx >= 0) {
		queue.items[idx] = item;
	} else {
		queue.items.push(item);
	}
	await saveReviewQueue(queue);
}
