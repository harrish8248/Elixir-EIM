import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ErrorState } from "./ErrorState";

describe("ErrorState Component", () => {
  it("renders title, message, error code and handles retry", () => {
    const handleRetry = vi.fn();
    render(
      <ErrorState
        title="Access Denied"
        message="PDP rejected authorization: Insufficient clearance level."
        errorCode="AUTHZ_PDP_DENY"
        onRetry={handleRetry}
      />
    );

    expect(screen.getByText("Access Denied")).toBeDefined();
    expect(screen.getByText(/PDP rejected authorization/)).toBeDefined();
    expect(screen.getByText("Code: AUTHZ_PDP_DENY")).toBeDefined();

    const retryBtn = screen.getByRole("button", { name: /Try Again/ });
    fireEvent.click(retryBtn);
    expect(handleRetry).toHaveBeenCalledTimes(1);
  });
});
