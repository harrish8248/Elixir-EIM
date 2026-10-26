/**
 * Elixir EIM Unified Enterprise Design Tokens.
 * Single source of truth for UI spacing, radii, shadows, typography, and density.
 */

export const tokens = {
  spacing: {
    base: "4px",
    xs: "4px",
    sm: "8px",
    md: "12px",
    lg: "16px",
    xl: "24px",
    "2xl": "32px",
    "3xl": "48px",
  },
  radii: {
    none: "0px",
    sm: "2px",
    md: "4px",
    lg: "6px",
    full: "9999px",
  },
  typography: {
    fontFamily: "'IBM Plex Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    sizes: {
      caption: "12px",
      bodyDense: "14px",
      body: "14px",
      subheading: "16px",
      title: "20px",
      hero: "24px",
      display: "32px",
    },
    weights: {
      regular: 400,
      medium: 500,
      semibold: 600,
      bold: 700,
    },
  },
  zIndex: {
    base: 0,
    dropdown: 1000,
    stickyHeader: 1020,
    modalBackdrop: 1040,
    modal: 1050,
    popover: 1060,
    toast: 1070,
  },
  density: {
    tableRowHeight: "36px",
    tableRowHeightCompact: "32px",
    buttonHeightSm: "28px",
    buttonHeightMd: "34px",
    inputHeight: "34px",
  },
  colors: {
    brandPrimary: "#0f172a", // Deep Navy
    brandAccent: "#2563eb",  // Interactive Accent
    surfaceLight: "#f8fafc",
    surfaceDark: "#0b0f19",
    borderLight: "#e2e8f0",
    borderDark: "#1e293b",
    statusSuccess: "#059669",
    statusWarning: "#d97706",
    statusDanger: "#dc2626",
    statusInfo: "#0284c7",
  },
} as const;

export type DesignTokens = typeof tokens;
