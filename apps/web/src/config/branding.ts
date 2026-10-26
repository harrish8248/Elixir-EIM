/**
 * Frontend Single Source of Truth for Product Branding & Corporate Identity.
 * Never hardcode product naming or labels directly inside UI components.
 */

export interface ProductBranding {
  name: string;
  shortName: string;
  productCode: string;
  version: string;
  buildVersion: string;
  apiVersion: string;
  vendor: string;
  copyright: string;
  supportUrl: string;
  docsUrl: string;
  trustLayerLabel: string;
}

export const BRANDING: ProductBranding = {
  name: "Elixir Enterprise Information Management",
  shortName: "Elixir EIM",
  productCode: "ELIXIR_EIM",
  version: "1.0.0",
  buildVersion: "1.0.0-build.20261026",
  apiVersion: "v1",
  vendor: "Elixir Enterprise Software Inc.",
  copyright: "© 2026 Elixir Enterprise Software Inc. All rights reserved.",
  supportUrl: "https://support.elixireim.internal",
  docsUrl: "https://docs.elixireim.internal",
  trustLayerLabel: "Elixir Trust Layer (Governance, Guardrails, & Audit)",
};
