import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Modal } from "./Modal";

describe("Modal Component", () => {
  it("renders when open is true", () => {
    render(
      <Modal open={true} onOpenChange={vi.fn()} title="Test Modal" description="Modal description">
        <div>Modal Content</div>
      </Modal>
    );
    expect(screen.getByText("Test Modal")).toBeDefined();
    expect(screen.getByText("Modal Content")).toBeDefined();
  });

  it("does not render content when open is false", () => {
    render(
      <Modal open={false} onOpenChange={vi.fn()} title="Hidden Modal">
        <div>Hidden Content</div>
      </Modal>
    );
    expect(screen.queryByText("Hidden Modal")).toBeNull();
  });
});
