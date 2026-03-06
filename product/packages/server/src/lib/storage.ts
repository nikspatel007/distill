import { createClient } from "@supabase/supabase-js";
import { getConfig } from "./config.js";

const BUCKET = "images";

function getStorageClient() {
  const config = getConfig();
  return createClient(config.SUPABASE_URL, config.SUPABASE_SERVICE_ROLE_KEY || config.SUPABASE_ANON_KEY);
}

export async function uploadImage(
  path: string,
  base64Data: string,
  mimeType: string,
): Promise<string | null> {
  try {
    const supabase = getStorageClient();
    const buffer = Buffer.from(base64Data, "base64");

    const { error } = await supabase.storage
      .from(BUCKET)
      .upload(path, buffer, {
        contentType: mimeType,
        upsert: true,
      });

    if (error) {
      console.warn(`Storage upload failed for ${path}:`, error.message);
      return null;
    }

    const { data } = supabase.storage.from(BUCKET).getPublicUrl(path);
    return data.publicUrl;
  } catch (err) {
    console.warn("Storage upload error:", err);
    return null;
  }
}
