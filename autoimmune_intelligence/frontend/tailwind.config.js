/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        surface: {
          0:   "#0a0b0f",
          1:   "#12131a",
          2:   "#1a1b25",
          3:   "#222330",
          4:   "#2a2c3b",
        },
        accent: {
          50:  "#eef5ff",
          100: "#d9e8ff",
          200: "#bcdbff",
          300: "#8ec5ff",
          400: "#59a5ff",
          500: "#3b82f6",
          600: "#2563eb",
          700: "#1d4ed8",
          800: "#1e40af",
          900: "#1e3a8a",
        },
        muted: {
          DEFAULT: "#6b7280",
          light: "#9ca3af",
          dim: "#4b5563",
        },
        cell:       "#34d399",
        cytokine:   "#f97316",
        pathway:    "#a78bfa",
        target:     "#3b82f6",
        gene:       "#f472b6",
        hypothesis: "#fbbf24",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
      },
    },
  },
  plugins: [],
};
