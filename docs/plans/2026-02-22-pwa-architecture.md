# PWA Architecture for Distill Web Dashboard

**Date:** 2026-02-22
**Author:** Architect Agent
**Status:** Proposal

---

## 1. Executive Summary

Convert the Distill web dashboard (Bun + Hono + React + Vite) into a Progressive Web App with offline caching, push notifications for pipeline events, and installability. The approach uses `vite-plugin-pwa` with Workbox for service worker management, the Web Push API with VAPID keys for notifications, and a JSON file-backed subscription store consistent with the existing content store pattern.

---

## 2. Service Worker Strategy

### 2.1 Why `vite-plugin-pwa` + Workbox (not custom SW)

- **Workbox** provides battle-tested runtime caching strategies, precache manifests, and cache expiration out of the box. Writing a custom service worker requires reimplementing all of this.
- **`vite-plugin-pwa`** (v0.21+) integrates directly with Vite's build pipeline: it generates the precache manifest from Vite's output, injects the SW registration script, and handles dev/prod modes cleanly.
- The plugin supports `injectManifest` mode, which gives us full control over the SW file while still getting the auto-generated precache manifest -- ideal since we need custom push notification handlers.
- Avoids maintaining a parallel build step for the service worker.

**Recommended version:** `vite-plugin-pwa@^0.21.0` (compatible with Vite 6).

### 2.2 Cache Strategies by Resource Type

| Resource | Strategy | Rationale |
|---|---|---|
| Static assets (JS, CSS, fonts, images in `/assets/`) | **CacheFirst** with max-age 30 days, max 60 entries | Vite hashes filenames; old versions naturally evict. |
| HTML shell (`/index.html`) | **StaleWhileRevalidate** | Ensures app loads instantly, picks up new deployments on next visit. |
| API GET: `/api/dashboard`, `/api/blog`, `/api/journal`, `/api/reading`, `/api/seeds`, `/api/notes`, `/api/memory` | **StaleWhileRevalidate** with max-age 1 hour, max 50 entries | Dashboard data should load fast but stay reasonably fresh. |
| API GET: `/api/studio/:slug` (studio item detail) | **NetworkFirst** with timeout 3s, fallback to cache | Always attempt fresh data for editing; fall back to cache if offline. |
| API GET: `/api/studio` (studio list) | **StaleWhileRevalidate** | List view can tolerate staleness. |
| Studio images (`/api/studio/images/*`) | **CacheFirst** with max-age 7 days, max 100 entries | Generated images are immutable once created. |
| Streaming endpoints (`/api/studio/:slug/chat`) | **NetworkOnly** | SSE/streaming cannot be cached. |
| Mutation endpoints (`POST`, `PUT`, `DELETE`) | **NetworkOnly** | Side-effecting; must hit server. |
| Pipeline endpoints (`/api/pipeline/*`) | **NetworkOnly** | Real-time status; no caching. |
| Push endpoints (`/api/push/*`) | **NetworkOnly** | Subscription management. |

### 2.3 Precaching

Precache the following for instant first load and offline shell:

- `index.html` (SPA shell)
- All Vite-generated JS/CSS chunks (auto-included via plugin manifest)
- `/favicon.svg`
- PWA icons (see section 5)

**Not precached** (fetched on demand):
- API data (varies per user/output dir)
- Studio images (large, generated dynamically)

### 2.4 SW Registration

Use `injectManifest` mode rather than `generateSW` because we need custom push event handlers. The plugin injects precache manifest into our custom SW source file.

---

## 3. Push Notification Architecture

### 3.1 Protocol: Web Push API + VAPID

VAPID (Voluntary Application Server Identification) provides a standard, cookie-free mechanism for server-to-browser push. No third-party push service needed.

**Library:** `web-push@^3.6.0` (npm package, works with Bun).

### 3.2 Server-Side Endpoints

New route file: `web/server/routes/push.ts`

```
POST   /api/push/subscribe     - Save a push subscription
DELETE /api/push/subscribe     - Remove a push subscription (by endpoint)
POST   /api/push/send          - Admin: trigger a notification to all subscribers
GET    /api/push/vapid-key     - Return the VAPID public key (for frontend)
```

**Schemas (in `shared/schemas.ts`):**

```typescript
export const PushSubscriptionSchema = z.object({
  endpoint: z.string().url(),
  keys: z.object({
    p256dh: z.string(),
    auth: z.string(),
  }),
});

export const PushNotificationPayloadSchema = z.object({
  title: z.string(),
  body: z.string(),
  icon: z.string().optional().default("/icons/icon-192.png"),
  badge: z.string().optional().default("/icons/badge-72.png"),
  tag: z.string().optional(),       // dedup key (e.g., "pipeline-run-123")
  data: z.object({
    url: z.string().optional(),     // URL to open on click
    type: z.string().optional(),    // "pipeline", "content", "summary"
  }).optional(),
  actions: z.array(z.object({
    action: z.string(),
    title: z.string(),
  })).optional(),
});
```

### 3.3 Subscription Storage

Store subscriptions in `{OUTPUT_DIR}/.push-subscriptions.json`:

```json
{
  "subscriptions": [
    {
      "endpoint": "https://fcm.googleapis.com/fcm/send/...",
      "keys": { "p256dh": "...", "auth": "..." },
      "created_at": "2026-02-22T10:00:00Z",
      "user_agent": "Mozilla/5.0 ..."
    }
  ]
}
```

This is consistent with the existing pattern (`.distill-content-store.json`, `.distill-notes.json`). The file lives alongside other state files in `OUTPUT_DIR`.

**Helper module:** `web/server/lib/push.ts`

```typescript
// Responsibilities:
// - loadSubscriptions() / saveSubscriptions()
// - addSubscription(sub) / removeSubscription(endpoint)
// - sendNotification(payload) -- iterates all subs, removes stale (410 Gone)
// - getVapidPublicKey()
```

### 3.4 VAPID Key Management

VAPID key pair stored in `{OUTPUT_DIR}/.vapid-keys.json`:

```json
{
  "publicKey": "BNxR...",
  "privateKey": "dGhp...",
  "subject": "mailto:distill@localhost"
}
```

On first server start (or first call to push route), if the file does not exist, auto-generate using `web-push.generateVAPIDKeys()` and persist. The `subject` field uses a placeholder `mailto:` (required by spec but can be any valid URL/email).

### 3.5 Notification Triggers

Three trigger points, all converging on the same `sendNotification()` helper:

#### Trigger 1: Pipeline Completion

In `web/server/routes/pipeline.ts`, the `child.on("close")` callback already tracks completion. Add a push notification call:

```typescript
child.on("close", (code) => {
  state.completedAt = new Date().toISOString();
  state.process = null;
  if (code === 0) {
    state.status = "completed";
    // NEW: Send push notification
    sendNotification({
      title: "Pipeline Complete",
      body: "Distill pipeline finished successfully.",
      tag: `pipeline-${Date.now()}`,
      data: { url: "/", type: "pipeline" },
    }).catch(() => {}); // Fire-and-forget
  } else {
    state.status = "failed";
    state.error = `Process exited with code ${code}`;
    sendNotification({
      title: "Pipeline Failed",
      body: `Pipeline exited with code ${code}.`,
      tag: `pipeline-${Date.now()}`,
      data: { url: "/", type: "pipeline" },
    }).catch(() => {});
  }
});
```

#### Trigger 2: New Content in ContentStore

In `web/server/lib/content-store.ts`, the `saveContentStore()` function is called whenever content is created or updated. Add an optional notification hook:

```typescript
// In saveContentStore(), after write:
export async function notifyNewContent(record: ContentStoreRecord): Promise<void> {
  await sendNotification({
    title: `New: ${record.title}`,
    body: `${record.content_type} content ready for review.`,
    tag: `content-${record.slug}`,
    data: { url: `/studio/${record.slug}`, type: "content" },
  });
}
```

Called from `studio.ts` when a new item is created via POST.

#### Trigger 3: External CLI Trigger

The Python CLI can call the web server API after `distill run`:

```bash
# In Python CLI (src/cli.py), after pipeline completion:
requests.post("http://localhost:6107/api/push/send", json={
    "title": "Daily Pipeline Complete",
    "body": "3 new journal entries, 1 blog post generated.",
    "data": {"url": "/", "type": "pipeline"}
})
```

This uses the `POST /api/push/send` admin endpoint. No auth needed since this is a local-only server.

### 3.6 Service Worker Push Handlers

In the custom SW file (`web/src/sw.ts`):

```typescript
self.addEventListener("push", (event) => {
  const data = event.data?.json() ?? {};
  const title = data.title ?? "Distill";
  const options = {
    body: data.body ?? "",
    icon: data.icon ?? "/icons/icon-192.png",
    badge: data.badge ?? "/icons/badge-72.png",
    tag: data.tag,
    data: data.data,
    actions: data.actions ?? [],
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = event.notification.data?.url ?? "/";

  // Handle action buttons
  if (event.action === "view") {
    // Same as default: open URL
  }

  event.waitUntil(
    clients.matchAll({ type: "window" }).then((windowClients) => {
      // Focus existing window if available
      for (const client of windowClients) {
        if (client.url.includes(self.location.origin) && "focus" in client) {
          client.navigate(url);
          return client.focus();
        }
      }
      // Otherwise open new window
      return clients.openWindow(url);
    })
  );
});
```

---

## 4. Offline Support

### 4.1 What Works Offline

| Feature | Offline? | How |
|---|---|---|
| Dashboard (summary view) | Yes | StaleWhileRevalidate cache |
| Journal entries (list + detail) | Yes | Cached on first visit |
| Blog posts (list + detail) | Yes | Cached on first visit |
| Reading digests | Yes | Cached on first visit |
| Studio list | Yes | StaleWhileRevalidate cache |
| Studio item detail | Partial | NetworkFirst falls back to cached version |
| Settings page | Yes | Static SPA route |

### 4.2 What Requires Network

| Feature | Why |
|---|---|
| Agent chat (streaming) | SSE/streaming, real-time LLM interaction |
| Publishing to Postiz/Ghost | External API calls |
| Pipeline runs | Spawns subprocess, real-time logs |
| Image generation | External API (Google GenAI) |
| Push subscription management | Requires server |

### 4.3 Offline Indicator UI

New component: `web/src/components/shared/OfflineIndicator.tsx`

Renders a top banner when `navigator.onLine === false` (+ `online`/`offline` event listeners). Placed in `__root.tsx` above the `<Outlet />`.

```
+------------------------------------------------------+
| You are offline. Some features may be unavailable.   |
+------------------------------------------------------+
|  [Sidebar]  |  [Content Area]                        |
```

- Yellow/amber banner, dismissible.
- Re-appears when connectivity drops again.
- Also shows a subtle indicator in the Sidebar (e.g., a dot next to the app name).

### 4.4 Offline Mutations Strategy

**Recommendation: Block, do not queue.**

Distill is a single-user local tool. Queuing mutations (IndexedDB-backed) adds substantial complexity (conflict resolution, retry logic, UI for pending queue). Since the server runs on localhost, offline scenarios are rare and brief (mostly laptop sleep/wake). A simple "you are offline" message on mutation attempts is sufficient.

If the user tries to publish or run pipeline while offline:
- Show toast: "This action requires a network connection."
- Do not queue the action.

---

## 5. Web App Manifest

### 5.1 Manifest Configuration

The manifest will be auto-generated by `vite-plugin-pwa` from the Vite config (not a separate `manifest.json` file). This keeps it in sync with the build.

```typescript
// In vite.config.ts (VitePWA plugin options):
manifest: {
  name: "Distill",
  short_name: "Distill",
  description: "Transform AI coding sessions into publishable content",
  display: "standalone",
  orientation: "any",
  start_url: "/",
  scope: "/",
  theme_color: "#18181b",    // zinc-900 (matches dark mode)
  background_color: "#09090b", // zinc-950
  categories: ["productivity", "developer-tools"],
  icons: [
    { src: "/icons/icon-72.png", sizes: "72x72", type: "image/png" },
    { src: "/icons/icon-96.png", sizes: "96x96", type: "image/png" },
    { src: "/icons/icon-128.png", sizes: "128x128", type: "image/png" },
    { src: "/icons/icon-144.png", sizes: "144x144", type: "image/png" },
    { src: "/icons/icon-152.png", sizes: "152x152", type: "image/png" },
    { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
    { src: "/icons/icon-384.png", sizes: "384x384", type: "image/png" },
    { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any maskable" },
  ],
  shortcuts: [
    {
      name: "Dashboard",
      short_name: "Home",
      url: "/",
      icons: [{ src: "/icons/icon-96.png", sizes: "96x96" }],
    },
    {
      name: "Studio",
      short_name: "Studio",
      url: "/studio",
      icons: [{ src: "/icons/icon-96.png", sizes: "96x96" }],
    },
    {
      name: "Journal",
      short_name: "Journal",
      url: "/journal",
      icons: [{ src: "/icons/icon-96.png", sizes: "96x96" }],
    },
  ],
}
```

### 5.2 Icon Generation

The existing `favicon.svg` (an alembic emoji `U+2697`) serves as the source. Generate all PNG sizes at build time or as a one-time script:

**Option A (recommended):** Use `@vite-pwa/assets-generator@^0.2.0` (companion to vite-plugin-pwa). Add a `pwa-assets.config.ts`:

```typescript
import { defineConfig } from "@vite-pwa/assets-generator/config";

export default defineConfig({
  preset: "minimal-2023",
  images: ["public/favicon.svg"],
});
```

Run once: `bunx pwa-assets-generator` to generate all required icon sizes into `public/icons/`.

**Option B:** Manual generation with sharp/Inkscape, committed to repo.

Option A is preferred because it auto-generates all sizes from the SVG source and is reproducible.

---

## 6. Server Changes

### 6.1 New Files

#### `web/server/routes/push.ts`

```typescript
// Endpoints:
// GET  /api/push/vapid-key    -> { publicKey: string }
// POST /api/push/subscribe    -> { ok: true }
// DELETE /api/push/subscribe  -> { ok: true }
// POST /api/push/send         -> { sent: number, failed: number }
```

Validation with `@hono/zod-validator` using `PushSubscriptionSchema` and `PushNotificationPayloadSchema`.

#### `web/server/lib/push.ts`

```typescript
// Core push notification logic:
//
// loadSubscriptions(): PushSubscription[]
// saveSubscriptions(subs: PushSubscription[]): void
// addSubscription(sub: PushSubscription): void
// removeSubscription(endpoint: string): void
// sendNotification(payload: PushPayload): Promise<{ sent: number; failed: number }>
// getOrCreateVapidKeys(): { publicKey: string; privateKey: string; subject: string }
// getVapidPublicKey(): string
//
// Uses `web-push` npm package for encryption and delivery.
// Automatically removes subscriptions that return 404/410 (expired).
```

### 6.2 Modified Files

| File | Change |
|---|---|
| `web/server/index.ts` | Import and mount `push` routes |
| `web/server/routes/pipeline.ts` | Call `sendNotification()` on pipeline completion/failure |
| `web/server/lib/config.ts` | Add optional `VAPID_SUBJECT` env var (default `mailto:distill@localhost`) |
| `web/shared/schemas.ts` | Add `PushSubscriptionSchema`, `PushNotificationPayloadSchema` |

### 6.3 Pipeline-to-Server Notification Flow

Three options, ranked by preference:

**Option A (recommended): Direct integration in pipeline.ts**

The web server already spawns the pipeline process in `pipeline.ts`. The `child.on("close")` handler is the natural place to fire push notifications. No external integration needed.

**Option B: CLI webhook**

Add a `--notify-url` flag to the Python CLI. After pipeline completes, POST to `http://localhost:6107/api/push/send`. Useful when pipeline runs outside the web server (e.g., cron job).

```python
# In src/cli.py after pipeline run:
if notify_url:
    requests.post(notify_url, json={"title": "Pipeline Complete", ...})
```

**Option C: File watcher on ContentStore**

Use `fs.watch()` on `.distill-content-store.json`. Complex, unreliable (OS-specific debouncing issues), and unnecessary given Options A/B.

**Recommendation:** Implement Option A first (zero new dependencies). Add Option B later if needed for cron/external triggers.

### 6.4 New Dependencies

| Package | Version | Purpose |
|---|---|---|
| `web-push` | `^3.6.0` | VAPID key generation, push encryption, delivery |
| `@types/web-push` | `^3.6.0` | TypeScript types (devDependency) |
| `vite-plugin-pwa` | `^0.21.0` | SW generation, manifest, precache (devDependency) |
| `@vite-pwa/assets-generator` | `^0.2.0` | Icon generation from SVG (devDependency) |

---

## 7. Build Pipeline Changes

### 7.1 Vite Configuration

```typescript
// web/vite.config.ts
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      strategies: "injectManifest",   // Custom SW for push handlers
      srcDir: "src",
      filename: "sw.ts",             // Our custom SW source
      registerType: "prompt",         // Prompt user to update, don't auto-reload
      injectRegister: false,          // We handle registration manually in main.tsx

      injectManifest: {
        globPatterns: ["**/*.{js,css,html,svg,png,woff2}"],
      },

      manifest: {
        // ... (see section 5.1 above)
      },

      devOptions: {
        enabled: true,    // Enable SW in dev mode for testing
        type: "module",
      },
    }),
  ],

  server: {
    port: 6108,
    proxy: {
      "/api": {
        target: "http://localhost:6107",
        changeOrigin: true,
      },
    },
  },

  resolve: {
    alias: {
      "@shared": new URL("./shared", import.meta.url).pathname,
      "@": new URL("./src", import.meta.url).pathname,
    },
  },
});
```

### 7.2 SW Registration in `main.tsx`

```typescript
// After createRoot(...).render(...)

// Register service worker
if ("serviceWorker" in navigator) {
  import("virtual:pwa-register").then(({ registerSW }) => {
    const updateSW = registerSW({
      onNeedRefresh() {
        // Show a toast/banner: "New version available. Click to update."
        // On user action: updateSW(true)
      },
      onOfflineReady() {
        // Show a toast: "App ready to work offline."
      },
    });
  });
}
```

### 7.3 TypeScript Configuration

Add `WebWorker` lib to `tsconfig.json` for SW types:

```json
{
  "compilerOptions": {
    "lib": ["ES2022", "DOM", "DOM.Iterable", "WebWorker"]
  }
}
```

Alternatively, create a separate `tsconfig.sw.json` for the service worker to avoid DOM/WebWorker type conflicts. The plugin handles this transparently.

### 7.4 Build Scripts

Update `package.json`:

```json
{
  "scripts": {
    "generate-pwa-assets": "pwa-assets-generator",
    "build": "vite build",
    "dev": "concurrently \"bun run dev:server\" \"bun run dev:client\""
  }
}
```

No changes to `build` or `dev` scripts -- `vite-plugin-pwa` hooks into the existing Vite pipeline automatically.

---

## 8. Frontend Notification Helpers

### 8.1 `web/src/lib/notifications.ts`

```typescript
// Responsibilities:
//
// getVapidKey(): Promise<string>
//   - Fetches /api/push/vapid-key
//   - Caches in memory
//
// subscribeToPush(): Promise<PushSubscription>
//   - Requests notification permission
//   - Gets VAPID key
//   - Calls registration.pushManager.subscribe()
//   - POSTs subscription to /api/push/subscribe
//   - Returns the subscription
//
// unsubscribeFromPush(): Promise<void>
//   - Gets current subscription
//   - Calls subscription.unsubscribe()
//   - DELETEs from /api/push/subscribe
//
// isPushSupported(): boolean
//   - Checks "serviceWorker" in navigator && "PushManager" in window
//
// getPermissionState(): NotificationPermission
//   - Returns Notification.permission ("granted" | "denied" | "default")
//
// isSubscribed(): Promise<boolean>
//   - Checks if pushManager has an active subscription
```

### 8.2 UI Integration

Add a notification toggle to the **Settings** page (`web/src/routes/settings.tsx`):

```
Notifications
  [Toggle: Enable push notifications]
  Status: Enabled / Disabled / Not supported

  When enabled, you'll be notified about:
  - Pipeline completions
  - New content ready for review
```

Also show a one-time prompt banner when the user first visits the dashboard:

```
Want to be notified when your pipeline finishes?
[Enable Notifications]  [Not now]
```

---

## 9. Complete File Structure

### New Files

```
web/
  public/
    icons/
      icon-72.png
      icon-96.png
      icon-128.png
      icon-144.png
      icon-152.png
      icon-192.png
      icon-384.png
      icon-512.png
      badge-72.png           # Notification badge (small monochrome)
  server/
    routes/push.ts           # Push subscription + send endpoints
    lib/push.ts              # web-push wrapper, subscription store
  src/
    sw.ts                    # Custom service worker (push + precache)
    lib/notifications.ts     # Subscribe/unsubscribe helpers
    components/
      shared/
        OfflineIndicator.tsx # Offline banner
        UpdatePrompt.tsx     # "New version available" banner
  pwa-assets.config.ts       # Icon generation config
```

### Modified Files

```
web/
  package.json               # Add web-push, vite-plugin-pwa, @vite-pwa/assets-generator
  vite.config.ts             # Add VitePWA plugin config
  tsconfig.json              # Add WebWorker lib (if needed)
  index.html                 # Add <meta name="theme-color"> (auto by plugin)
  server/index.ts            # Mount push routes
  server/routes/pipeline.ts  # Add push notification on completion
  server/lib/config.ts       # Add VAPID_SUBJECT env var
  shared/schemas.ts          # Add push-related Zod schemas
  src/main.tsx               # Add SW registration
  src/routes/__root.tsx      # Add OfflineIndicator + UpdatePrompt
  src/routes/settings.tsx    # Add notification toggle UI
```

---

## 10. Security Considerations

### 10.1 VAPID Keys

- Auto-generated on first use, stored in `OUTPUT_DIR/.vapid-keys.json`.
- The private key never leaves the server.
- Add `.vapid-keys.json` to `.gitignore`.
- The `subject` field (`mailto:` or URL) is required by the Web Push spec but has no functional impact for local use.

### 10.2 Subscription Validation

- Validate subscription shape with Zod (`PushSubscriptionSchema`) on `POST /api/push/subscribe`.
- The `endpoint` must be a valid URL (enforced by Zod's `z.string().url()`).
- Automatically remove stale subscriptions: if `web-push.sendNotification()` returns 404 or 410, delete from store.

### 10.3 Rate Limiting

- Push notifications should be rate-limited server-side to prevent flooding:
  - Max 1 notification per `tag` per 5 minutes (dedup by tag).
  - Max 10 notifications per hour across all subscribers.
- Implement as a simple in-memory map: `tag -> lastSentAt`. No need for Redis.

### 10.4 HTTPS Requirement

- Web Push requires a secure context. `localhost` is treated as secure by browsers, so development works.
- For LAN access (e.g., `http://192.168.x.x:6107`), push subscriptions will fail. Options:
  - Use a local HTTPS proxy (Caddy already in the stack for Postiz).
  - Use a `.local` domain with mDNS + self-signed cert.
  - Accept that push only works on localhost; LAN users get the PWA shell without push.
- **Recommendation:** Document that push notifications require `localhost` or HTTPS. Do not add complexity for LAN HTTPS at this stage.

### 10.5 File Permissions

- `.vapid-keys.json` and `.push-subscriptions.json` should have restrictive permissions (600). The server can set this on write.
- These files should be excluded from any backup/sync that goes to public storage.

---

## 11. Implementation Phases

### Phase 1: Installable PWA (Minimal)
- Add `vite-plugin-pwa` with manifest config
- Generate icons from favicon.svg
- Basic service worker with precaching (no push yet)
- Offline indicator component
- Update prompt component
- **Estimated scope:** 5 new files, 3 modified files

### Phase 2: Push Notifications
- Add `web-push` dependency
- VAPID key generation and storage
- Push subscription endpoints
- Pipeline completion notifications
- Settings page toggle
- **Estimated scope:** 4 new files, 4 modified files

### Phase 3: Advanced Caching
- Runtime caching strategies for all API routes
- Cache expiration and cleanup
- Offline fallback pages
- **Estimated scope:** 1 modified file (sw.ts)

### Phase 4: Enhanced Notifications
- Content creation notifications
- CLI webhook (`--notify-url`)
- Notification action buttons
- Notification grouping
- **Estimated scope:** 2 modified files

---

## 12. Testing Strategy

### Service Worker Tests

- Unit test cache strategy configuration (Workbox config validation)
- Integration test: verify precache manifest includes expected assets after build
- Manual test: install PWA, go offline, verify cached pages load

### Push Notification Tests

- Unit test `web/server/lib/push.ts` (load/save subscriptions, VAPID key generation)
- Unit test `web/server/routes/push.ts` (endpoint validation, subscribe/unsubscribe)
- Mock `web-push.sendNotification()` in tests (avoid real push calls)
- Test file: `web/server/__tests__/push.test.ts`

### Frontend Tests

- Unit test `notifications.ts` helpers with mocked `PushManager`
- Component test `OfflineIndicator.tsx` with mocked `navigator.onLine`
- Component test `UpdatePrompt.tsx` with mocked SW registration

### E2E Tests

- Playwright test: verify manifest is served correctly
- Playwright test: verify SW registers in production build
- Playwright test: verify offline indicator appears when network is disabled

---

## 13. Key Decisions Summary

| Decision | Choice | Rationale |
|---|---|---|
| SW management | `vite-plugin-pwa` + `injectManifest` | Auto precache manifest + custom push handlers |
| SW update strategy | `prompt` (not `autoUpdate`) | User controls when to reload; avoids mid-session disruption |
| Push library | `web-push` | Standard, well-maintained, works with Bun |
| Subscription storage | JSON file in OUTPUT_DIR | Consistent with existing `.distill-*` pattern |
| VAPID keys | Auto-generated, file-persisted | Zero config for users |
| Offline mutations | Block (show error) | Simpler than queuing; local server rarely offline |
| Notification trigger | Pipeline `child.on("close")` | Already in the codebase, zero new deps |
| Icon generation | `@vite-pwa/assets-generator` | One-time generation from existing SVG |
| LAN push | Not supported (localhost only) | Avoid HTTPS complexity for local-first tool |
