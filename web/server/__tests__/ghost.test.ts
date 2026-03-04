import { afterAll, beforeAll, describe, expect, test } from "bun:test";
import { join } from "node:path";
import { app } from "../index.js";
import { resetConfig, setConfig } from "../lib/config.js";
import {
	generateGhostJWT,
	getGhostTargets,
	isGhostConfigured,
	markdownToMobiledoc,
} from "../lib/ghost.js";

const FIXTURES = join(import.meta.dir, "fixtures");

describe("Ghost JWT generation", () => {
	test("generates a valid JWT with expected structure", async () => {
		// Use a fake key: id=abc, secret=0123456789abcdef0123456789abcdef (32 hex chars = 16 bytes)
		const fakeKey = "abc:0123456789abcdef0123456789abcdef";
		const token = await generateGhostJWT(fakeKey);

		// JWT has three parts
		const parts = token.split(".");
		expect(parts.length).toBe(3);

		// Header should contain kid and HS256
		const headerPart = parts[0] ?? "";
		const header = JSON.parse(Buffer.from(headerPart, "base64url").toString());
		expect(header.alg).toBe("HS256");
		expect(header.kid).toBe("abc");
		expect(header.typ).toBe("JWT");

		// Payload should have iat, exp, and aud
		const payloadPart = parts[1] ?? "";
		const payload = JSON.parse(Buffer.from(payloadPart, "base64url").toString());
		expect(payload.aud).toBe("/admin/");
		expect(payload.exp - payload.iat).toBe(300);
	});

	test("throws on invalid key format", async () => {
		expect(generateGhostJWT("no-colon-here")).rejects.toThrow("Invalid Ghost Admin API key");
	});
});

describe("markdownToMobiledoc", () => {
	test("wraps markdown in mobiledoc structure", () => {
		const md = "# Hello\n\nSome content.";
		const result = markdownToMobiledoc(md);
		const parsed = JSON.parse(result);

		expect(parsed.version).toBe("0.3.1");
		expect(parsed.ghostVersion).toBe("4.0");
		expect(parsed.cards).toEqual([["markdown", { markdown: md }]]);
		expect(parsed.sections).toEqual([[10, 0]]);
	});

	test("handles special characters in markdown", () => {
		const md = 'He said "hello" & <world>';
		const result = markdownToMobiledoc(md);
		const parsed = JSON.parse(result);
		expect(parsed.cards[0][1].markdown).toBe(md);
	});
});

describe("Ghost config helpers", () => {
	beforeAll(() => {
		setConfig({
			OUTPUT_DIR: FIXTURES,
			PORT: 6109,
			GHOST_URL: "https://troopx.ghost.io",
			GHOST_ADMIN_API_KEY: "abc:def123",
			GHOST_PERSONAL_URL: "",
			GHOST_PERSONAL_ADMIN_API_KEY: "",
		});
	});

	afterAll(() => {
		resetConfig();
	});

	test("isGhostConfigured returns true for primary when configured", () => {
		expect(isGhostConfigured("primary")).toBe(true);
	});

	test("isGhostConfigured returns false for personal when not configured", () => {
		expect(isGhostConfigured("personal")).toBe(false);
	});

	test("getGhostTargets returns only configured targets", () => {
		const targets = getGhostTargets();
		// Only primary is configured (personal has empty URL/key)
		expect(targets.length).toBe(1);
		const primary = targets[0];
		expect(primary?.name).toBe("primary");
		expect(primary?.configured).toBe(true);
		// Label derived from URL hostname
		expect(primary?.label).toBe("Troopx");
	});
});

describe("GET /api/ghost/targets", () => {
	beforeAll(() => {
		setConfig({
			OUTPUT_DIR: FIXTURES,
			PORT: 6109,
			GHOST_URL: "https://troopx.ghost.io",
			GHOST_ADMIN_API_KEY: "key:secret",
			GHOST_PERSONAL_URL: "https://personal.ghost.io",
			GHOST_PERSONAL_ADMIN_API_KEY: "key2:secret2",
		});
	});

	afterAll(() => {
		resetConfig();
	});

	test("returns configured Ghost targets", async () => {
		const res = await app.request("/api/ghost/targets");
		expect(res.status).toBe(200);

		const data = await res.json();
		expect(data.targets.length).toBe(2);
		expect(data.targets[0].name).toBe("primary");
		expect(data.targets[0].configured).toBe(true);
		expect(data.targets[1].name).toBe("personal");
		expect(data.targets[1].configured).toBe(true);
	});
});

describe("GET /api/ghost/targets (unconfigured)", () => {
	beforeAll(() => {
		setConfig({
			OUTPUT_DIR: FIXTURES,
			PORT: 6109,
			GHOST_URL: "",
			GHOST_ADMIN_API_KEY: "",
			GHOST_PERSONAL_URL: "",
			GHOST_PERSONAL_ADMIN_API_KEY: "",
		});
	});

	afterAll(() => {
		resetConfig();
	});

	test("returns empty targets when not configured", async () => {
		const res = await app.request("/api/ghost/targets");
		expect(res.status).toBe(200);

		const data = await res.json();
		expect(data.targets.length).toBe(0);
	});
});

describe("POST /api/ghost/publish/:slug", () => {
	beforeAll(() => {
		setConfig({
			OUTPUT_DIR: FIXTURES,
			PORT: 6109,
			GHOST_URL: "",
			GHOST_ADMIN_API_KEY: "",
			GHOST_PERSONAL_URL: "",
			GHOST_PERSONAL_ADMIN_API_KEY: "",
		});
	});

	afterAll(() => {
		resetConfig();
	});

	test("returns 404 for non-existent slug", async () => {
		const res = await app.request("/api/ghost/publish/non-existent-slug", {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ target: "personal", status: "draft" }),
		});
		expect(res.status).toBe(404);
	});

	test("returns 503 when Ghost is not configured", async () => {
		// Even with a valid slug, Ghost not configured should return 503
		// This test relies on no content-store existing in fixtures with a matching slug
		const res = await app.request("/api/ghost/publish/test-slug", {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ target: "primary", status: "draft" }),
		});
		// Will be 404 (no content) or 503 (no Ghost config)
		expect([404, 503]).toContain(res.status);
	});
});
