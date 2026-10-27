import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ConfirmDialog } from "./ConfirmDialog";

describe("ConfirmDialog Component", () => {
  it("renders title, message, and trigger buttons", () => {
    const handleConfirm = vi.fn();
    const handleCancel = vi.fn();

    render(
      <ConfirmDialog
        open={true}
        onOpenChange={vi.fn()}
        title="Lift Legal Hold"
        message="Are you sure you want to lift Legal Hold #891? This action requires step-up MFA."
        confirmLabel="Lift Hold"
        variant="danger"
        onConfirm={handleConfirm}
        onCancel={handleCancel}
      />
    );

    expect(screen.getByText("Lift Legal Hold")).toBeDefined();
    expect(screen.getByText(/Are you sure you want to lift Legal Hold/)).toBeDefined();

    const confirmBtn = screen.getByText("Lift Hold");
    fireEvent.click(confirmBtn);
    expect(handleConfirm).toHaveBeenCalledTimes(1);
  });
});
