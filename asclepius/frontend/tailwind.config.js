/** @type {import('tailwindcss').Config} */
const v = (name) => `rgb(var(--c-${name}) / <alpha-value>)`;

module.exports = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./hooks/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Every colour reads a theme variable (see app/globals.css), so a theme
        // is only a block of values. The neutral ramp has five steps.
        bg: { DEFAULT: v("bg"), 2: v("bg-2"), 3: v("bg-3"), 4: v("bg-3") },
        line: { DEFAULT: v("line"), 2: v("line-2") },
        ink: { DEFAULT: v("ink"), 2: v("ink") },
        muted: { DEFAULT: v("muted"), light: v("ink"), dim: v("faint") },
        faint: v("faint"),

        // The accent. `green` is the historical name; it now means "accent".
        green: {
          DEFAULT: v("accent"),
          2: v("accent-fg"),
          deep: v("accent"),
          hi: v("accent-hi"),
          faint: "rgb(var(--c-accent) / 0.14)",
        },
        accent: {
          50: v("accent-fg"), 100: v("accent-fg"), 200: v("accent-fg"), 300: v("accent-fg"),
          400: v("accent-fg"), 500: v("accent"), 600: v("accent"), 700: v("accent"),
          800: v("accent"), 900: v("accent"),
        },
        "on-accent": v("on-accent"),

        // Semantic colours are for risk and status only, never decoration.
        ok: v("ok"),
        warn: v("warn"),
        bad: v("bad"),
        amber: v("warn"),
        risk: v("bad"),

        // Legacy aliases, collapsed onto the ramp above.
        surface: { 0: v("bg"), 1: v("bg-2"), 2: v("bg-3"), 3: v("line"), 4: v("line-2") },
        gray: { 100: v("ink"), 200: v("ink"), 300: v("ink"), 400: v("muted"), 500: v("faint"), 600: v("faint") },
        red: { 300: v("bad"), 400: v("bad"), 500: v("bad") },
        yellow: { 400: v("warn"), 500: v("warn") },
        emerald: { 400: v("ok"), 500: v("ok") },
        blue: { 400: v("ink"), 500: v("ink") },
        purple: { 400: v("muted"), 500: v("muted") },
        pink: { 400: v("accent-fg"), 500: v("accent-fg") },
        cyan: { 400: v("muted"), 500: v("muted") },
        cell: v("muted"), cytokine: v("muted"), pathway: v("muted"),
        target: v("accent-fg"), gene: v("accent-fg"), hypothesis: v("warn"),
      },
      fontFamily: {
        display: ["var(--font-geist-sans)", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        sans: ["var(--font-geist-sans)", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        mono: ["var(--font-geist-mono)", "ui-monospace", "monospace"],
        // Identifiers only (PMIDs, gene symbols, code).
        code: ["var(--font-geist-mono)", "ui-monospace", "monospace"],
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
        card: "0 12px 40px rgb(0 0 0 / 0.35)",
        "glow-green": "0 0 14px rgb(var(--c-accent) / 0.25)",
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
