"use client";

import { useEffect, useState } from "react";
import { type Theme, applyTheme, getStoredTheme, setStoredTheme } from "@/lib/theme";

const ICONS: Record<Theme, string> = {
  light: "☀️",
  dark: "🌙",
  system: "💻",
};

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>("system");

  useEffect(() => {
    const stored = getStoredTheme();
    setTheme(stored);
    applyTheme(stored);
  }, []);

  const cycle = () => {
    const order: Theme[] = ["light", "dark", "system"];
    const next = order[(order.indexOf(theme) + 1) % order.length];
    setTheme(next);
    setStoredTheme(next);
  };

  return (
    <button
      onClick={cycle}
      title={`Theme: ${theme}`}
      className="rounded-lg px-2 py-1 text-sm text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800 dark:text-gray-400 transition-colors"
    >
      {ICONS[theme]}
    </button>
  );
}
