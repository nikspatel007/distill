/// Service Worker for Distill PWA
/// Strategy: network-first for API, cache-first for static assets, offline fallback

const CACHE_NAME = "distill-v1";
const OFFLINE_URL = "/offline.html";

// Static assets to pre-cache on install
const PRECACHE_URLS = ["/", "/offline.html", "/manifest.json", "/favicon.svg"];

// --- Install: pre-cache shell ---
self.addEventListener("install", (event) => {
	event.waitUntil(
		caches
			.open(CACHE_NAME)
			.then((cache) => cache.addAll(PRECACHE_URLS))
			.then(() => self.skipWaiting()),
	);
});

// --- Activate: clean old caches ---
self.addEventListener("activate", (event) => {
	event.waitUntil(
		caches
			.keys()
			.then((keys) =>
				Promise.all(
					keys
						.filter((key) => key !== CACHE_NAME)
						.map((key) => caches.delete(key)),
				),
			)
			.then(() => self.clients.claim()),
	);
});

// --- Fetch: route-based caching strategies ---
self.addEventListener("fetch", (event) => {
	const { request } = event;
	const url = new URL(request.url);

	// Skip non-GET requests
	if (request.method !== "GET") return;

	// Skip chrome-extension and other non-http(s) protocols
	if (!url.protocol.startsWith("http")) return;

	// API requests: network-first, no cache fallback
	if (url.pathname.startsWith("/api/")) {
		event.respondWith(networkFirst(request));
		return;
	}

	// Static assets (JS, CSS, images, fonts): cache-first
	if (isStaticAsset(url.pathname)) {
		event.respondWith(cacheFirst(request));
		return;
	}

	// Navigation requests (HTML pages): network-first with offline fallback
	if (request.mode === "navigate") {
		event.respondWith(networkFirstWithOffline(request));
		return;
	}

	// Everything else: network-first
	event.respondWith(networkFirst(request));
});

// --- Caching strategies ---

async function networkFirst(request) {
	try {
		const response = await fetch(request);
		if (response.ok) {
			const cache = await caches.open(CACHE_NAME);
			cache.put(request, response.clone());
		}
		return response;
	} catch {
		const cached = await caches.match(request);
		if (cached) return cached;
		return new Response("Network error", { status: 503 });
	}
}

async function cacheFirst(request) {
	const cached = await caches.match(request);
	if (cached) return cached;

	try {
		const response = await fetch(request);
		if (response.ok) {
			const cache = await caches.open(CACHE_NAME);
			cache.put(request, response.clone());
		}
		return response;
	} catch {
		return new Response("Network error", { status: 503 });
	}
}

async function networkFirstWithOffline(request) {
	try {
		const response = await fetch(request);
		if (response.ok) {
			const cache = await caches.open(CACHE_NAME);
			cache.put(request, response.clone());
		}
		return response;
	} catch {
		const cached = await caches.match(request);
		if (cached) return cached;
		return caches.match(OFFLINE_URL);
	}
}

function isStaticAsset(pathname) {
	return /\.(js|css|png|jpg|jpeg|gif|svg|ico|woff2?|ttf|eot)$/.test(pathname);
}
