import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // Institutional Enterprise Navy & Slate
        brand: {
          50: "#f0f6fe",
          100: "#dde9fc",
          200: "#c2daf9",
          300: "#98c3f5",
          400: "#67a2ee",
          500: "#3b82f6",
          600: "#2563eb", // Primary interactive accent
          700: "#1d4ed8",
          800: "#1e40af",
          900: "#1e3a8a", // Navy Header & Brand
          950: "#0f172a", // Dark Primary Shell
        },
        surface: {
          50: "#f8fafc",
          100: "#f1f5f9",
          200: "#e2e8f0",
          300: "#cbd5e1",
          400: "#94a3b8",
          500: "#64748b",
          600: "#475569",
          700: "#334155",
          800: "#1e293b",
          900: "#0f172a",
          950: "#0b0f19",
        },
        // Semantic Status Colors (Only for records, hold, risk, and approval states)
        status: {
          success: "#059669",
          warning: "#d97706",
          danger: "#dc2626", // Legal Hold / Critical Purge
          info: "#0284c7",
        },
      },
      fontFamily: {
        sans: [
          "IBM Plex Sans",
          "Inter",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
        mono: ["JetBrains Mono", "Fira Code", "Courier New", "monospace"],
      },
      fontSize: {
        xs: ["12px", { lineHeight: "16px" }],
        sm: ["14px", { lineHeight: "20px" }], // Dense body 14px
        base: ["16px", { lineHeight: "24px" }],
        lg: ["18px", { lineHeight: "26px" }],
        xl: ["20px", { lineHeight: "28px" }],
        "2xl": ["24px", { lineHeight: "32px" }],
        "3xl": ["32px", { lineHeight: "40px" }],
      },
      spacing: {
        // Strict 4px base scale
        "0.5": "2px",
        "1": "4px",
        "2": "8px",
        "3": "12px",
        "4": "16px",
        "5": "20px",
        "6": "24px",
        "8": "32px",
        "10": "40px",
        "12": "48px",
        "16": "64px",
      },
    },
  },
  plugins: [],
};

export default config;
