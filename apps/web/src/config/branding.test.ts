import { describe, it, expect } from "vitest";
import { BRANDING } from "../config/branding";

describe("Frontend Branding Single Source of Truth", () => {
  it("defines required product naming and version metadata", () => {
    expect(BRANDING.name).toBe("Elixir Enterprise Information Management");
    expect(BRANDING.shortName).toBe("Elixir EIM");
    expect(BRANDING.productCode).toBe("ELIXIR_EIM");
    expect(BRANDING.version).toBe("1.0.0");
    expect(BRANDING.apiVersion).toBe("v1");
    expect(BRANDING.copyright).toContain("Elixir Enterprise Software Inc.");
  });
});
