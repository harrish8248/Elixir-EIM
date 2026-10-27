import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Toast } from "./Toast";

describe("Toast Component", () => {
  it("renders title, message, and handles close", () => {
    const handleClose = vi.fn();
    render(
      <Toast
        type="success"
        title="Audit Sealed"
        message="Cryptographic proof block persisted to PostgreSQL."
        onClose={handleClose}
      />
    );

    expect(screen.getByText("Audit Sealed")).toBeDefined();
    expect(screen.getByText(/Cryptographic proof block persisted/)).toBeDefined();

    const closeBtn = screen.getByRole("button", { name: "Dismiss notification" });
    fireEvent.click(closeBtn);
    expect(handleClose).toHaveBeenCalledTimes(1);
  });
});
