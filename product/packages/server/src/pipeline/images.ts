import { GoogleGenAI } from "@google/genai";

let _client: GoogleGenAI | null = null;

function getClient(): GoogleGenAI | null {
  if (_client) return _client;
  const apiKey = process.env.GOOGLE_AI_API_KEY;
  if (!apiKey) return null;
  _client = new GoogleGenAI({ apiKey });
  return _client;
}

export function isImageGenConfigured(): boolean {
  return !!process.env.GOOGLE_AI_API_KEY;
}

export interface GeneratedImage {
  base64: string;
  mimeType: string;
  prompt: string;
}

export async function generateImage(prompt: string): Promise<GeneratedImage | null> {
  const client = getClient();
  if (!client) return null;

  try {
    const stylePrefix = "Cinematic photorealistic photograph, high contrast lighting, cool blue-tinted shadows, clean minimalist composition, shallow depth of field. No text, no logos, no UI elements. ";
    const fullPrompt = stylePrefix + prompt;

    const response = await client.models.generateImages({
      model: "imagen-3.0-generate-002",
      prompt: fullPrompt,
      config: {
        numberOfImages: 1,
      },
    });

    const image = response.generatedImages?.[0];
    if (!image?.image?.imageBytes) return null;

    return {
      base64: image.image.imageBytes,
      mimeType: "image/png",
      prompt: fullPrompt,
    };
  } catch (error) {
    console.warn("Image generation failed:", error);
    return null;
  }
}

export async function generateHighlightImages(
  highlights: Array<{ title: string; imagePrompt: string | null }>,
): Promise<Map<string, GeneratedImage>> {
  const results = new Map<string, GeneratedImage>();
  if (!isImageGenConfigured()) return results;

  const promises = highlights
    .filter((h) => h.imagePrompt)
    .map(async (h) => {
      const image = await generateImage(h.imagePrompt!);
      if (image) {
        results.set(h.title, image);
      }
    });

  await Promise.allSettled(promises);
  return results;
}
