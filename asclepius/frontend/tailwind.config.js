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
          DEFAULT: "#0c1014", // page
          2: "#131820",       // card surface
          3: "#1b2230",       // nested surface
          4: "#243042",       // thumbs / inputs
        },
        line: {
          DEFAULT: "#232a36", // hairline
          2: "#39434f",       // interactive border / strong divider
        },
        ink: {
          DEFAULT: "#f3f6f8", // primary text
          2: "#d3d8de",       // body
        },
        faint: "#565e6b",
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
          0: "#0c1014",
          1: "#131820",
          2: "#1b2230",
          3: "#232a36",
          4: "#2e3744",
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
          DEFAULT: "#8a929e",
          light: "#d3d8de",
          dim: "#565e6b",
        },
        // Category tones — disciplined onto neutral + green + amber
        cell:       "#8a929e",
        cytokine:   "#8a929e",
        pathway:    "#8a929e",
        target:     "#87f085",
        gene:       "#87f085",
        hypothesis: "#f5c062",
        // Override default scales used for state so they read Helix
        gray: {
          100: "#f3f6f8",
          200: "#d3d8de",
          300: "#d3d8de",
          400: "#8a929e",
          500: "#565e6b",
          600: "#565e6b",
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
          400: "#d3d8de",
          500: "#d3d8de",
        },
        purple: {
          400: "#8a929e",
          500: "#8a929e",
        },
        pink: {
          400: "#87f085",
          500: "#87f085",
        },
        cyan: {
          400: "#8a929e",
          500: "#8a929e",
        },
      },
      fontFamily: {
        display: ["var(--font-newsreader)", "Georgia", "serif"],
        sans: ["var(--font-inter)", "var(--font-geist-sans)", "system-ui", "sans-serif"],
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
