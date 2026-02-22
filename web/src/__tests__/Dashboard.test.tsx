import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, test } from "vitest";
import DailyBriefing from "../routes/index.js";
import { handlers } from "./mocks/handlers.js";

// Mock TanStack Router's Link to render as a plain <a>
vi.mock("@tanstack/react-router", () => ({
	Link: ({
		children,
		to,
		params,
		...props
	}: { children: React.ReactNode; to: string; params?: Record<string, string>; [key: string]: unknown }) => {
		let href = to;
		if (params) {
			for (const [key, value] of Object.entries(params)) {
				href = href.replace(`$${key}`, value);
			}
		}
		return (
			<a href={href} {...props}>
				{children}
			</a>
		);
	},
}));

const server = setupServer(...handlers);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function renderWithProviders(ui: React.ReactElement) {
	const qc = new QueryClient({
		defaultOptions: { queries: { retry: false } },
	});
	return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("DailyBriefing", () => {
	test("displays loading state initially", () => {
		renderWithProviders(<DailyBriefing />);
		expect(screen.getByText("Loading briefing...")).toBeInTheDocument();
	});

	test("displays journal card with brief bullets", async () => {
		renderWithProviders(<DailyBriefing />);
		await waitFor(() => {
			expect(screen.getByText("What you built")).toBeInTheDocument();
		});
		expect(screen.getByText(/Built the content pipeline/)).toBeInTheDocument();
		expect(screen.getByText(/Added multi-platform publishing/)).toBeInTheDocument();
		expect(screen.getByText(/3 sessions/)).toBeInTheDocument();
	});

	test("displays intake card with highlights", async () => {
		renderWithProviders(<DailyBriefing />);
		await waitFor(() => {
			expect(screen.getByText("What you read")).toBeInTheDocument();
		});
		expect(screen.getByText(/AI agent patterns article/)).toBeInTheDocument();
		expect(screen.getByText(/12 items/)).toBeInTheDocument();
	});

	test("displays publish queue with approve button", async () => {
		renderWithProviders(<DailyBriefing />);
		await waitFor(() => {
			expect(screen.getByText("Ready to publish")).toBeInTheDocument();
		});
		expect(screen.getByText("Week 6: Building the Pipeline")).toBeInTheDocument();
		expect(screen.getByText("draft")).toBeInTheDocument();
		expect(screen.getByText("Approve")).toBeInTheDocument();
		expect(screen.getByText("Edit in Studio")).toBeInTheDocument();
	});

	test("displays seeds with develop and dismiss buttons", async () => {
		renderWithProviders(<DailyBriefing />);
		await waitFor(() => {
			expect(screen.getByText("Ideas")).toBeInTheDocument();
		});
		expect(screen.getByText("Write about multi-agent patterns")).toBeInTheDocument();
		expect(screen.getByText("Compare RAG vs fine-tuning")).toBeInTheDocument();
		const developLinks = screen.getAllByText("Develop");
		expect(developLinks.length).toBe(2);
	});

	test("displays date navigation with Today pill hidden when on today", async () => {
		renderWithProviders(<DailyBriefing />);
		await waitFor(() => {
			expect(screen.getByText("What you built")).toBeInTheDocument();
		});
		// Today pill should not be visible when date is "today"
		expect(screen.queryByText("Today")).not.toBeInTheDocument();
		// Navigation arrows should be present
		expect(screen.getByLabelText("Previous day")).toBeInTheDocument();
		expect(screen.getByLabelText("Next day")).toBeInTheDocument();
	});

	test("shows Today pill after navigating to previous day", async () => {
		renderWithProviders(<DailyBriefing />);
		await waitFor(() => {
			expect(screen.getByText("What you built")).toBeInTheDocument();
		});
		fireEvent.click(screen.getByLabelText("Previous day"));
		await waitFor(() => {
			expect(screen.getByText("Today")).toBeInTheDocument();
		});
	});

	test("shows empty states when no data", async () => {
		server.use(
			http.get("/api/home/:date", () => {
				return HttpResponse.json({
					date: "2026-02-09",
					journal: {
						brief: [],
						hasFullEntry: false,
						date: "2026-02-09",
						sessionsCount: 0,
						durationMinutes: 0,
					},
					intake: {
						highlights: [],
						itemCount: 0,
						hasFullDigest: false,
						date: "2026-02-09",
					},
					publishQueue: [],
					seeds: [],
				});
			}),
		);
		renderWithProviders(<DailyBriefing />);
		await waitFor(() => {
			expect(screen.getByText("No journal entry for this date")).toBeInTheDocument();
		});
		expect(screen.getByText("No intake digest for this date")).toBeInTheDocument();
		expect(screen.getByText("Nothing to publish")).toBeInTheDocument();
		// Seeds card should not render at all when empty
		expect(screen.queryByText("Ideas")).not.toBeInTheDocument();
	});

	test("displays journal Read more link when full entry exists", async () => {
		renderWithProviders(<DailyBriefing />);
		await waitFor(() => {
			expect(screen.getByText("What you built")).toBeInTheDocument();
		});
		const readMoreLinks = screen.getAllByText("Read more");
		expect(readMoreLinks.length).toBeGreaterThanOrEqual(1);
		// Journal Read more link should point to /journal/2026-02-09
		const journalLink = readMoreLinks[0]!;
		expect(journalLink.closest("a")).toHaveAttribute("href", "/journal/2026-02-09");
	});

	test("displays error state on fetch failure", async () => {
		server.use(
			http.get("/api/home/:date", () => {
				return new HttpResponse(null, { status: 500 });
			}),
		);
		renderWithProviders(<DailyBriefing />);
		await waitFor(() => {
			expect(screen.getByText(/Error: Failed to load briefing/)).toBeInTheDocument();
		});
	});
});
