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
        // ---- Helix named tokens (preferred) ----
        bg: {
          DEFAULT: "#0b0c0e", // page
          2: "#111316",       // card surface
          3: "#181a1e",       // nested surface
          4: "#202327",       // thumbs / inputs
        },
        line: {
          DEFAULT: "#1d2025", // hairline
          2: "#2c3036",       // interactive border / strong divider
        },
        ink: {
          DEFAULT: "#ededef", // primary text
          2: "#c5c8ce",       // body
        },
        faint: "#5b6068",
        // Signature — signal only
        green: {
          DEFAULT: "#87f085",
          2: "#4dca60",
          deep: "#1a7a3a",
          faint: "rgba(135,240,133,0.10)",
        },
        // Semantic — warnings only
        amber: "#f5c062",
        risk: "#f08987",

        // ---- Legacy aliases remapped onto the Helix scale ----
        // (existing components reference these; they now render Helix tokens)
        surface: {
          0: "#0b0c0e",
          1: "#111316",
          2: "#181a1e",
          3: "#1d2025",
          4: "#272a30",
        },
        accent: {
          50:  "#eafdea",
          100: "#c9f8c8",
          200: "#aef4ac",
          300: "#87f085",
          400: "#87f085",
          500: "#87f085",
          600: "#4dca60",
          700: "#1a7a3a",
          800: "#176b33",
          900: "#0f4a24",
        },
        muted: {
          DEFAULT: "#868b94",
          light: "#c5c8ce",
          dim: "#5b6068",
        },
        // Category tones — disciplined onto neutral + green + amber
        cell:       "#868b94",
        cytokine:   "#868b94",
        pathway:    "#868b94",
        target:     "#87f085",
        gene:       "#87f085",
        hypothesis: "#f5c062",
        // Override default scales used for state so they read Helix
        gray: {
          100: "#ededef",
          200: "#c5c8ce",
          300: "#c5c8ce",
          400: "#868b94",
          500: "#5b6068",
          600: "#5b6068",
        },
        red: {
          300: "#f4a8a6",
          400: "#f08987",
          500: "#f08987",
        },
        yellow: {
          400: "#f5c062",
          500: "#f5c062",
        },
        emerald: {
          400: "#87f085",
          500: "#87f085",
        },
        // Compare A/B + Hypothesis category tags — disciplined onto the
        // neutral scale and the signature green (distinction via layout/labels).
        blue: {
          400: "#c5c8ce",
          500: "#c5c8ce",
        },
        purple: {
          400: "#868b94",
          500: "#868b94",
        },
        pink: {
          400: "#87f085",
          500: "#87f085",
        },
        cyan: {
          400: "#868b94",
          500: "#868b94",
        },
      },
      fontFamily: {
        display: ["var(--font-geist-sans)", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        sans: ["var(--font-geist-sans)", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        mono: ["var(--font-geist-mono)", "ui-monospace", "monospace"],
      },
      fontSize: {
        // Helix type ramp (px → rem)
        "display-xl": ["4rem",     { lineHeight: "0.95", letterSpacing: "-0.025em" }], // 64
        "display-l":  ["2.375rem", { lineHeight: "1.1",  letterSpacing: "-0.02em"  }], // 38
        "display-m":  ["1.375rem", { lineHeight: "1.35", letterSpacing: "-0.01em"  }], // 22
        "body-l":     ["1.0625rem",{ lineHeight: "1.55" }],                            // 17
        body:         ["0.875rem", { lineHeight: "1.55" }],                            // 14
        small:        ["0.75rem",  { lineHeight: "1.55" }],                            // 12
        kicker:       ["0.625rem", { lineHeight: "1.4", letterSpacing: "0.18em" }],    // 10
      },
      borderRadius: {
        sm: "6px", md: "8px", lg: "10px", xl: "14px",
      },
      boxShadow: {
        card: "0 12px 40px rgba(0,0,0,0.40), inset 0 1px 0 rgba(255,255,255,0.02)",
        "glow-green": "0 0 12px rgba(135,240,133,0.18)",
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
