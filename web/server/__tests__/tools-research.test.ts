import { describe, expect, test } from "bun:test";

describe("Research tools", () => {
	test("extractReadableText strips HTML to text", async () => {
		const { extractReadableText } = await import("../tools/research.js");
		const html =
			"<html><body><nav>Menu</nav><article><h1>Title</h1><p>Content paragraph.</p></article><footer>Footer</footer></body></html>";
		const text = extractReadableText(html);
		expect(text).toContain("Title");
		expect(text).toContain("Content paragraph");
		expect(text).not.toContain("Menu");
		expect(text).not.toContain("Footer");
	});

	test("extractReadableText handles plain text gracefully", async () => {
		const { extractReadableText } = await import("../tools/research.js");
		const plainText = "This is just plain text with no HTML tags.";
		const result = extractReadableText(plainText);
		expect(result).toBe(plainText);
	});

	test("extractReadableText prefers article content when long enough", async () => {
		const { extractReadableText } = await import("../tools/research.js");
		const html = `
			<html>
				<body>
					<nav>Navigation menu</nav>
					<article>
						<h1>Main Article Title</h1>
						<p>This is a substantial article with enough content to be preferred over the body text. It contains multiple sentences and provides valuable information that should be extracted as the primary content.</p>
					</article>
					<aside>Sidebar content</aside>
					<footer>Footer text</footer>
				</body>
			</html>
		`;
		const text = extractReadableText(html);
		expect(text).toContain("Main Article Title");
		expect(text).toContain("substantial article");
		expect(text).not.toContain("Navigation menu");
		expect(text).not.toContain("Sidebar content");
		expect(text).not.toContain("Footer text");
	});

	test("extractReadableText prefers main content when article is too short", async () => {
		const { extractReadableText } = await import("../tools/research.js");
		const html = `
			<html>
				<body>
					<article>Short</article>
					<main>
						<h1>Main Content Area</h1>
						<p>This is the main content area with substantial text that should be extracted instead of the short article tag.</p>
					</main>
				</body>
			</html>
		`;
		const text = extractReadableText(html);
		expect(text).toContain("Main Content Area");
		expect(text).toContain("substantial text");
	});

	test("extractReadableText falls back to body when no article or main", async () => {
		const { extractReadableText } = await import("../tools/research.js");
		const html = `
			<html>
				<body>
					<div>
						<h1>Title in div</h1>
						<p>Content in a div element.</p>
					</div>
				</body>
			</html>
		`;
		const text = extractReadableText(html);
		expect(text).toContain("Title in div");
		expect(text).toContain("Content in a div element");
	});

	test("extractReadableText removes script and style tags", async () => {
		const { extractReadableText } = await import("../tools/research.js");
		const html = `
			<html>
				<head>
					<style>.class { color: red; }</style>
				</head>
				<body>
					<script>console.log('test');</script>
					<article>
						<h1>Clean Content</h1>
						<p>This should be extracted without scripts or styles.</p>
					</article>
				</body>
			</html>
		`;
		const text = extractReadableText(html);
		expect(text).toContain("Clean Content");
		expect(text).not.toContain("console.log");
		expect(text).not.toContain("color: red");
	});
});
