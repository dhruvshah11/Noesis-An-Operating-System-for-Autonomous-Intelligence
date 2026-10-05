import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: "class",
  theme: {
    container: {
      center: true,
      padding: "1rem",
      screens: { "2xl": "1440px" },
    },
    extend: {
      fontFamily: {
        sans: ["var(--font-inter)", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      colors: {
        brand: {
          50: "#eef4ff",
          100: "#dbe7ff",
          200: "#bcd2ff",
          300: "#8eb3ff",
          400: "#5988ff",
          500: "#3462ff",
          600: "#1f43f5",
          700: "#1a33dc",
          800: "#1c2db1",
          900: "#1e2e8c",
          950: "#141c52",
        },
        "brand-purple": "#6E56CF",
        ink: {
          50: "#f6f7fb",
          100: "#eceff6",
          200: "#d6dceb",
          300: "#b0bbd5",
          400: "#8393b9",
          500: "#61739e",
          600: "#4c5b84",
          700: "#3e4a6b",
          800: "#353e59",
          900: "#2f364b",
          950: "#1b1f2e",
        },
      },
      boxShadow: {
        soft: "0 1px 2px rgba(16,24,40,0.04), 0 1px 3px rgba(16,24,40,0.06)",
        card: "0 4px 8px -2px rgba(16,24,40,0.06), 0 10px 24px -8px rgba(16,24,40,0.08)",
      },
      keyframes: {
        "fade-in": {
          "0%": { opacity: "0", transform: "translateY(4px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "fade-in": "fade-in 180ms ease-out both",
      },
    },
  },
  plugins: [],
};

export default config;
