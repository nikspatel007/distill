import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, test } from "vitest";
import Publish from "../routes/publish.js";
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

describe("Publish", () => {
	test("displays queue items after loading", async () => {
		renderWithProviders(<Publish />);
		await waitFor(() => {
			expect(screen.getByText("Week 6: Building the Pipeline")).toBeInTheDocument();
		});
		expect(screen.getByText("twitter")).toBeInTheDocument();
	});

	test("shows Postiz not configured note", async () => {
		renderWithProviders(<Publish />);
		await waitFor(() => {
			expect(screen.getByText(/Connect Postiz/)).toBeInTheDocument();
		});
	});
});
