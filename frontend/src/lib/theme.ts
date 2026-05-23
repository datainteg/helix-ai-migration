"use client";

export type Theme = "light" | "dark" | "system";

export function applyTheme(theme: Theme): void {
  const root = document.documentElement;
  if (theme === "dark") {
    root.classList.add("dark");
  } else if (theme === "light") {
    root.classList.remove("dark");
  } else {
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    root.classList.toggle("dark", prefersDark);
  }
}

export function getStoredTheme(): Theme {
  return (localStorage.getItem("helix-theme") as Theme) || "system";
}

export function setStoredTheme(theme: Theme): void {
  localStorage.setItem("helix-theme", theme);
  applyTheme(theme);
}
