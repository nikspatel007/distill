import { useEffect, useRef } from "react";
import { useShareIntentContext } from "expo-share-intent";
import { useRouter } from "expo-router";
import { apiFetch } from "./api";
import { setPendingShareUrl } from "./shareIntentState";

/**
 * Extracts a valid HTTP(S) URL from a share intent, or returns null.
 */
function extractUrl(shareIntent: {
  webUrl?: string | null;
  text?: string | null;
}): string | null {
  const raw = shareIntent.webUrl ?? shareIntent.text ?? null;
  if (!raw) return null;
  const trimmed = raw.trim();
  if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) {
    return trimmed;
  }
  return null;
}

/**
 * Handles incoming share intents (URLs shared from Safari/Chrome share sheet).
 *
 * When a URL is shared into the app:
 * - If authenticated: auto-submits to POST /api/share, navigates to share tab
 * - If not authenticated: stores the URL as pending so the share tab can
 *   pre-fill it after login
 *
 * Must be used inside ShareIntentProvider and AuthProvider.
 */
export function useIncomingShareIntent(opts: { isAuthenticated: boolean }) {
  const { hasShareIntent, shareIntent, resetShareIntent } =
    useShareIntentContext();
  const router = useRouter();
  const processingRef = useRef(false);

  useEffect(() => {
    if (!hasShareIntent || processingRef.current) return;

    const url = extractUrl(shareIntent ?? {});
    if (!url) {
      resetShareIntent();
      return;
    }

    // If not authenticated, store the URL for later and let the
    // auth redirect handle navigation to login
    if (!opts.isAuthenticated) {
      setPendingShareUrl(url);
      resetShareIntent();
      return;
    }

    processingRef.current = true;

    // Auto-submit to the API
    apiFetch("/share", {
      method: "POST",
      body: JSON.stringify({ url }),
    })
      .then(() => {
        router.replace("/(tabs)/share");
      })
      .catch((err) => {
        console.error("Failed to share URL from intent:", err);
        // Store URL so the share tab can pre-fill it for manual retry
        setPendingShareUrl(url);
        router.replace("/(tabs)/share");
      })
      .finally(() => {
        resetShareIntent();
        processingRef.current = false;
      });
  }, [hasShareIntent, opts.isAuthenticated, shareIntent, resetShareIntent, router]);
}
