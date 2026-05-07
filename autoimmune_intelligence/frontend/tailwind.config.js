/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./hooks/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        surface: {
          0: "#09090f",   // deepest background
          1: "#0f1018",   // sidebar / cards
          2: "#161720",   // hover states
          3: "#1e2030",   // borders
          4: "#272940",   // subtle highlights
        },
        // Teal/cyan biology theme
        accent: {
          50:  "#f0fdfa",
          100: "#ccfbf1",
          200: "#99f6e4",
          300: "#5eead4",
          400: "#2dd4bf",
          500: "#14b8a6",
          600: "#0d9488",
          700: "#0f766e",
          800: "#115e59",
          900: "#134e4a",
        },
        muted: {
          DEFAULT: "#6b7280",
          light: "#9ca3af",
          dim: "#4b5563",
        },
        // Semantic biology colours
        cell:       "#34d399",   // emerald — immune cells
        cytokine:   "#fb923c",   // orange — cytokines
        pathway:    "#a78bfa",   // violet — pathways
        target:     "#38bdf8",   // sky — therapeutic targets
        gene:       "#f472b6",   // pink — genes
        hypothesis: "#fbbf24",   // amber — hypotheses
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
      },
      animation: {
        "fade-in":   "fadeIn 0.2s ease-in-out",
        "slide-in":  "slideIn 0.25s cubic-bezier(0.16,1,0.3,1)",
        "pulse-dot": "pulseDot 1.4s ease-in-out infinite",
      },
      keyframes: {
        fadeIn: {
          "0%":   { opacity: "0" },
          "100%": { opacity: "1" },
        },
        slideIn: {
          "0%":   { opacity: "0", transform: "translateX(16px)" },
          "100%": { opacity: "1", transform: "translateX(0)" },
        },
        pulseDot: {
          "0%, 80%, 100%": { opacity: "0.2", transform: "scale(0.8)" },
          "40%":            { opacity: "1",   transform: "scale(1)" },
        },
      },
    },
  },
  plugins: [],
};
