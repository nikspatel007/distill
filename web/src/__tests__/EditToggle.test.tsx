import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";
import { EditToggle } from "../components/shared/EditToggle.js";

describe("EditToggle", () => {
	test("renders Edit button in preview mode", () => {
		render(
			<EditToggle
				isEditing={false}
				onToggle={vi.fn()}
				onSave={vi.fn()}
				isSaving={false}
				isDirty={false}
				saveSuccess={false}
			/>,
		);
		expect(screen.getByText("Edit")).toBeInTheDocument();
		expect(screen.queryByText("Save")).not.toBeInTheDocument();
	});

	test("renders Preview and Save buttons in edit mode", () => {
		render(
			<EditToggle
				isEditing={true}
				onToggle={vi.fn()}
				onSave={vi.fn()}
				isSaving={false}
				isDirty={true}
				saveSuccess={false}
			/>,
		);
		expect(screen.getByText("Preview")).toBeInTheDocument();
		expect(screen.getByText("Save")).toBeInTheDocument();
	});

	test("calls onToggle when Edit/Preview clicked", () => {
		const onToggle = vi.fn();
		render(
			<EditToggle
				isEditing={false}
				onToggle={onToggle}
				onSave={vi.fn()}
				isSaving={false}
				isDirty={false}
				saveSuccess={false}
			/>,
		);
		fireEvent.click(screen.getByText("Edit"));
		expect(onToggle).toHaveBeenCalledOnce();
	});

	test("calls onSave when Save clicked", () => {
		const onSave = vi.fn();
		render(
			<EditToggle
				isEditing={true}
				onToggle={vi.fn()}
				onSave={onSave}
				isSaving={false}
				isDirty={true}
				saveSuccess={false}
			/>,
		);
		fireEvent.click(screen.getByText("Save"));
		expect(onSave).toHaveBeenCalledOnce();
	});

	test("disables Save when not dirty", () => {
		render(
			<EditToggle
				isEditing={true}
				onToggle={vi.fn()}
				onSave={vi.fn()}
				isSaving={false}
				isDirty={false}
				saveSuccess={false}
			/>,
		);
		expect(screen.getByText("Save")).toBeDisabled();
	});

	test("disables Save when saving", () => {
		render(
			<EditToggle
				isEditing={true}
				onToggle={vi.fn()}
				onSave={vi.fn()}
				isSaving={true}
				isDirty={true}
				saveSuccess={false}
			/>,
		);
		expect(screen.getByText("Saving...")).toBeDisabled();
	});

	test("shows Saved flash", () => {
		render(
			<EditToggle
				isEditing={true}
				onToggle={vi.fn()}
				onSave={vi.fn()}
				isSaving={false}
				isDirty={false}
				saveSuccess={true}
			/>,
		);
		expect(screen.getByText("Saved")).toBeInTheDocument();
	});
});
