import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, test } from "vitest";
import Dashboard from "../routes/index.js";
import { handlers } from "./mocks/handlers.js";

// Mock TanStack Router's Link to render as a plain <a>
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

describe("Dashboard", () => {
	test("displays loading state initially", () => {
		renderWithProviders(<Dashboard />);
		expect(screen.getByText("Loading dashboard...")).toBeInTheDocument();
	});

	test("displays dashboard stats after loading", async () => {
		renderWithProviders(<Dashboard />);
		await waitFor(() => {
			expect(screen.getByText("5")).toBeInTheDocument();
		});
		expect(screen.getByText("Journal entries")).toBeInTheDocument();
		expect(screen.getByText("3")).toBeInTheDocument();
		expect(screen.getByText("Blog posts")).toBeInTheDocument();
	});

	test("displays recent journal entries", async () => {
		renderWithProviders(<Dashboard />);
		await waitFor(() => {
			expect(screen.getByText("2026-02-09")).toBeInTheDocument();
		});
		expect(screen.getByText("Recent Journal Entries")).toBeInTheDocument();
	});

	test("displays active threads", async () => {
		renderWithProviders(<Dashboard />);
		await waitFor(() => {
			expect(screen.getByText("content-pipeline")).toBeInTheDocument();
		});
		expect(screen.getByText("Building the content pipeline")).toBeInTheDocument();
	});

	test("displays seed and note counts", async () => {
		renderWithProviders(<Dashboard />);
		await waitFor(() => {
			expect(screen.getByText("2 pending seeds")).toBeInTheDocument();
		});
		expect(screen.getByText("1 active editorial notes")).toBeInTheDocument();
	});
});
