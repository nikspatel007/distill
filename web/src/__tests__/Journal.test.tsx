import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, test } from "vitest";
import JournalList from "../routes/journal.js";
import { handlers } from "./mocks/handlers.js";

vi.mock("@tanstack/react-router", () => ({
	Link: ({
		children,
		to,
		...props
	}: { children: React.ReactNode; to: string; [key: string]: unknown }) => (
		<a href={to} {...props}>
			{children}
		</a>
	),
}));

vi.mock("../components/shared/DateBadge.js", () => ({
	DateBadge: ({ date }: { date: string }) => <span>{date}</span>,
}));

vi.mock("../components/shared/TagBadge.js", () => ({
	TagBadge: ({ tag }: { tag: string }) => <span>{tag}</span>,
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

describe("JournalList", () => {
	test("displays loading state", () => {
		renderWithProviders(<JournalList />);
		expect(screen.getByText("Loading journal...")).toBeInTheDocument();
	});

	test("displays journal entries after loading", async () => {
		renderWithProviders(<JournalList />);
		await waitFor(() => {
			expect(screen.getByText("2026-02-09")).toBeInTheDocument();
		});
		expect(screen.getByText("2026-02-08")).toBeInTheDocument();
	});

	test("displays session counts", async () => {
		renderWithProviders(<JournalList />);
		await waitFor(() => {
			expect(screen.getByText("3 sessions, 120m")).toBeInTheDocument();
		});
		expect(screen.getByText("2 sessions, 90m")).toBeInTheDocument();
	});

	test("displays project badges", async () => {
		renderWithProviders(<JournalList />);
		await waitFor(() => {
			expect(screen.getByText("distill")).toBeInTheDocument();
		});
		expect(screen.getByText("vermas")).toBeInTheDocument();
	});
});
