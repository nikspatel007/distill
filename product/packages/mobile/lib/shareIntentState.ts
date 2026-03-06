/**
 * Simple module-level state to communicate a pending shared URL
 * from the share intent handler to the share tab.
 *
 * When a URL is shared via the OS share sheet but the auto-submit
 * fails (e.g., user not authenticated), the URL is stored here
 * so the share tab can pre-fill it for manual submission.
 */

let pendingUrl: string | null = null;

export function setPendingShareUrl(url: string | null) {
  pendingUrl = url;
}

export function consumePendingShareUrl(): string | null {
  const url = pendingUrl;
  pendingUrl = null;
  return url;
}
