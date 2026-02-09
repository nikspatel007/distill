import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";
import { MarkdownRenderer } from "../components/shared/MarkdownRenderer.js";

describe("MarkdownRenderer", () => {
	test("renders basic markdown", () => {
		render(<MarkdownRenderer content="# Hello World" />);
		expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Hello World");
	});

	test("renders paragraphs", () => {
		render(<MarkdownRenderer content="This is a paragraph." />);
		expect(screen.getByText("This is a paragraph.")).toBeInTheDocument();
	});

	test("converts Obsidian wiki links [[target]] to anchor links", () => {
		render(<MarkdownRenderer content="See [[my-note]] for details." />);
		const link = screen.getByRole("link", { name: "my-note" });
		expect(link).toBeInTheDocument();
		expect(link).toHaveAttribute("href", "#my-note");
	});

	test("converts Obsidian wiki links with labels [[target|label]]", () => {
		render(<MarkdownRenderer content="See [[my-note|My Note]] for details." />);
		const link = screen.getByRole("link", { name: "My Note" });
		expect(link).toBeInTheDocument();
		expect(link).toHaveAttribute("href", "#my-note");
	});

	test("renders GFM tables", () => {
		const table = `| Col A | Col B |
| --- | --- |
| val1 | val2 |`;
		render(<MarkdownRenderer content={table} />);
		expect(screen.getByRole("table")).toBeInTheDocument();
		expect(screen.getByText("val1")).toBeInTheDocument();
	});

	test("renders inline code", () => {
		render(<MarkdownRenderer content="Use `distill run` to start." />);
		expect(screen.getByText("distill run")).toBeInTheDocument();
	});

	test("renders lists", () => {
		render(<MarkdownRenderer content={"- Item 1\n- Item 2\n- Item 3"} />);
		expect(screen.getByText("Item 1")).toBeInTheDocument();
		expect(screen.getByText("Item 2")).toBeInTheDocument();
		expect(screen.getByText("Item 3")).toBeInTheDocument();
	});
});
