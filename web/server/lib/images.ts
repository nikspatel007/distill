/**
 * Image generation via Google GenAI (Nano Banana Pro / Gemini).
 *
 * Mirrors src/shared/images.py — same mood-based style prefixes,
 * same graceful fallback when not configured.
 */
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const DEFAULT_MODEL = "gemini-2.0-flash-preview-image-generation";

/** Mood-indexed style prefixes — identical to Python ImageGenerator. */
export const STYLE_PREFIXES: Record<string, string> = {
	reflective:
		"Contemplative editorial photograph. Diffused overcast light, cool blue-grey palette with desaturated tones. 50mm lens at f/4, moderate depth of field. Symmetrical composition with deliberate negative space. Still, quiet atmosphere. No text, no logos, no UI elements. -- ",
	energetic:
		"Dynamic editorial photograph. Warm golden-hour directional light casting long shadows. 35mm lens at f/2.8, shallow depth of field. Diagonal composition with strong leading lines and a sense of forward motion. Amber and warm-white palette. No text, no logos, no UI elements. -- ",
	cautionary:
		"Tense editorial photograph. Hard directional lighting from a single source, deep shadows with teal-and-orange color contrast. 85mm lens at f/2, tight crop with the subject off-center. Unsettled atmosphere. No text, no logos, no UI elements. -- ",
	triumphant:
		"Bold editorial photograph. Bright high-key lighting, vivid saturated colors. 24mm wide-angle lens at f/8 for deep focus. Expansive composition with a sense of scale and openness. The scene feels earned and resolved. No text, no logos, no UI elements. -- ",
	intimate:
		"Quiet editorial photograph. Soft window light from camera-left, warm muted earth tones with cream and amber highlights. 85mm lens at f/1.8, very shallow depth of field isolating the subject. Close framing, personal scale. No text, no logos, no UI elements. -- ",
	technical:
		"Precise editorial photograph. Clean even studio lighting, cool neutral palette with high clarity. 100mm macro lens or overhead bird's-eye view. Geometric composition with ordered elements. Clinical but elegant. No text, no logos, no UI elements. -- ",
	playful:
		"Whimsical editorial photograph. Bright diffused daylight, slightly warm with pastel accent colors. 35mm lens at f/4, moderate depth. Off-kilter composition with an element of surprise or visual humor. Light and approachable atmosphere. No text, no logos, no UI elements. -- ",
	somber:
		"Subdued editorial photograph. Low-key lighting with chiaroscuro contrast, desaturated palette leaning toward cool greys and muted blues. 135mm telephoto compression, f/2.8. Isolated subject with heavy negative space. Bleach-bypass tonal quality. No text, no logos, no UI elements. -- ",
};

// biome-ignore lint/complexity/useLiteralKeys: tsc noPropertyAccessFromIndexSignature
const DEFAULT_STYLE = STYLE_PREFIXES["reflective"] ?? "";

export interface ImageResult {
	filename: string;
	relativePath: string;
	prompt: string;
	mood: string;
}

/**
 * Check whether image generation is available.
 */
export function isImageConfigured(): boolean {
	// biome-ignore lint/complexity/useLiteralKeys: tsc noPropertyAccessFromIndexSignature
	return !!process.env["GOOGLE_AI_API_KEY"];
}

/**
 * Generate an image from a text prompt and save to disk.
 *
 * Returns metadata on success, null if not configured or on error.
 */
export async function generateImage(
	prompt: string,
	options: {
		outputDir: string;
		mood?: string;
		slug?: string;
		aspectRatio?: string;
	},
): Promise<ImageResult | null> {
	if (!isImageConfigured()) {
		return null;
	}

	const {
		outputDir,
		mood = "reflective",
		slug = "image",
		aspectRatio: _aspectRatio = "16:9",
	} = options;
	const style = STYLE_PREFIXES[mood] ?? DEFAULT_STYLE;
	const fullPrompt = style + prompt;

	try {
		const { GoogleGenAI } = await import("@google/genai");
		// biome-ignore lint/complexity/useLiteralKeys: tsc noPropertyAccessFromIndexSignature
		const ai = new GoogleGenAI({ apiKey: process.env["GOOGLE_AI_API_KEY"] ?? "" });

		const response = await ai.models.generateContent({
			model: DEFAULT_MODEL,
			contents: fullPrompt,
			config: {
				responseModalities: ["TEXT", "IMAGE"],
			},
		});

		const parts = response.candidates?.[0]?.content?.parts ?? [];
		for (const part of parts) {
			if (part.inlineData?.data) {
				const timestamp = Date.now();
				const filename = `${slug}-${timestamp}.png`;
				const imagesDir = join(outputDir, "studio", "images");
				mkdirSync(imagesDir, { recursive: true });
				const filePath = join(imagesDir, filename);
				const buffer = Buffer.from(part.inlineData.data, "base64");
				writeFileSync(filePath, buffer);

				return {
					filename,
					relativePath: `studio/images/${filename}`,
					prompt,
					mood,
				};
			}
		}

		return null;
	} catch (err) {
		console.error("Image generation failed:", err instanceof Error ? err.message : err);
		return null;
	}
}
