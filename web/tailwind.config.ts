import type { Config } from "tailwindcss"
export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        teal: {
          50: "#f0fdfa",
          100: "#ccfbf1",
          200: "#99f6e4",
          300: "#5eead4",
          400: "#2dd4bf",
          500: "#14b8a6",
          600: "#0F766E", // primary action color
          700: "#0d5f59",
          800: "#0b4d49",
          900: "#09403d",
        },
        amber: {
          600: "#B45309", // secondary / editorial warmth
          700: "#A16207", // warning
        },
        canvas: "#F6F1E8",
        surface: "#FFFDFC",
        "surface-2": "#F0E7DB",
        line: "#D8D0C4",
        ink: "#1F2937",
        muted: "#5F6B76",
        success: {
          DEFAULT: "#2F6B4F",
          50: "#f0fdf4",
          100: "#dcfce7",
          200: "#bbf7d0",
        },
        warning: "#A16207",
        error: {
          DEFAULT: "#B42318",
          50: "#fef2f2",
          100: "#fee2e2",
          200: "#fecaca",
        },
      },
    },
  },
  plugins: [],
} satisfies Config
