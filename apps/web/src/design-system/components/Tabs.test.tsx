import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Tabs } from "./Tabs";

describe("Tabs Component", () => {
  it("renders tab triggers and active content", () => {
    render(
      <Tabs
        items={[
          { id: "audit", label: "Audit Ledger", content: <div>Audit Events Table</div> },
          { id: "proof", label: "Hash Chain", content: <div>SHA-256 Chain Visualizer</div> },
        ]}
      />
    );

    expect(screen.getByText("Audit Ledger")).toBeDefined();
    expect(screen.getByText("Audit Events Table")).toBeDefined();
    expect(screen.getByText("Hash Chain")).toBeDefined();
  });

  it("renders specific tab content when controlled value is provided", () => {
    render(
      <Tabs
        value="proof"
        items={[
          { id: "audit", label: "Audit Ledger", content: <div>Audit Events Table</div> },
          { id: "proof", label: "Hash Chain", content: <div>SHA-256 Chain Visualizer</div> },
        ]}
      />
    );

    expect(screen.getByText("SHA-256 Chain Visualizer")).toBeDefined();
  });
});
