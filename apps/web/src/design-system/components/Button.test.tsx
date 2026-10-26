import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Button } from "./Button";

describe("Button Design System Primitive", () => {
  it("renders with default primary enterprise style", () => {
    render(<Button>Upload Document</Button>);
    const button = screen.getByRole("button", { name: "Upload Document" });
    expect(button).toBeDefined();
    expect(button.className).toContain("bg-brand-900");
  });

  it("handles loading state and disables click", () => {
    render(<Button isLoading>Processing</Button>);
    const button = screen.getByRole("button");
    expect(button.hasAttribute("disabled")).toBe(true);
  });
});
