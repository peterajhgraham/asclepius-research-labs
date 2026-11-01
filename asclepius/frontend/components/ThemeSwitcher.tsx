"use client";

import { useEffect, useState } from "react";

export const THEMES = [
  { id: "ember", label: "Ember", swatch: "#f47030" },
  { id: "indigo", label: "Indigo", swatch: "#6366f1" },
  { id: "lagoon", label: "Lagoon", swatch: "#2dd4bf" },
  { id: "paper", label: "Paper", swatch: "linear-gradient(135deg, #f7f5f0 50%, #c2410c 50%)" },
] as const;

type ThemeId = (typeof THEMES)[number]["id"];

/** Small colour-way picker. The choice is remembered in this browser (and `?theme=` works on any URL). */
export default function ThemeSwitcher() {
  const [theme, setTheme] = useState<ThemeId>("ember");

  useEffect(() => {
    const current = document.documentElement.getAttribute("data-theme") as ThemeId | null;
    if (current && THEMES.some((t) => t.id === current)) setTheme(current);
  }, []);

  function choose(id: ThemeId) {
    setTheme(id);
    document.documentElement.setAttribute("data-theme", id);
    try {
      localStorage.setItem("asclepius-theme", id);
    } catch {
      /* storage can be unavailable (private mode); the choice just won't persist */
    }
  }

  return (
    <div className="flex items-center justify-between px-4 py-3">
      <span className="text-xs text-faint">Theme</span>
      <div className="flex items-center gap-1.5" role="radiogroup" aria-label="Colour theme">
        {THEMES.map((t) => {
          const active = theme === t.id;
          return (
            <button
              key={t.id}
              type="button"
              role="radio"
              aria-checked={active}
              aria-label={t.label}
              title={t.label}
              onClick={() => choose(t.id)}
              className={`h-4 w-4 rounded-full transition ${
                active ? "ring-2 ring-ink/70 ring-offset-2 ring-offset-bg-2" : "opacity-70 hover:opacity-100"
              }`}
              style={{ background: t.swatch }}
            />
          );
        })}
      </div>
    </div>
  );
}
