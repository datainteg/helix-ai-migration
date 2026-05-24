"use client";

/**
 * Theme + tweaks store — persists per-user UI preferences in localStorage and
 * pushes the resolved values onto the document root as CSS variables. The
 * TweaksPanel (open from Topbar) drives this; the Settings page reads + writes
 * the same store so changes round-trip.
 *
 * Storage key: `helix-tweaks` (Zustand persist).
 *
 * NOTE: This is a frontend-only store. No backend round-trip yet — adding
 * user_preferences to the backend's User model is a future task.
 */

import { create } from "zustand";
import { persist } from "zustand/middleware";

export type ThemeMode = "light" | "dark" | "auto";
export type Density = "compact" | "regular" | "comfy";

export interface TweaksState {
  // Theme
  theme: ThemeMode;
  density: Density;
  fontSizePx: number;          // 11.5–16
  // Brand accent — overrides --con-brand at runtime.
  primaryColor: string;        // hex
  // Surface tone — slight warm/cool tint applied to --con-bg.
  surfaceTint: "warm" | "neutral" | "cool";

  // Setters
  setTheme: (t: ThemeMode) => void;
  setDensity: (d: Density) => void;
  setFontSize: (n: number) => void;
  setPrimaryColor: (hex: string) => void;
  setSurfaceTint: (t: "warm" | "neutral" | "cool") => void;
  reset: () => void;
}

const DEFAULTS = {
  theme: "light" as ThemeMode,
  density: "regular" as Density,
  fontSizePx: 13.5,
  primaryColor: "#4F46E5",
  surfaceTint: "warm" as const,
};

const DENSITY_MULTIPLIER: Record<Density, number> = {
  compact: 0.8,
  regular: 1.0,
  comfy: 1.2,
};

const SURFACE_TINTS: Record<"warm" | "neutral" | "cool", { bg: string; bg2: string; surface: string }> = {
  warm:    { bg: "#FAFAF7", bg2: "#F4F3EF", surface: "#FFFFFF" },
  neutral: { bg: "#FAFAFA", bg2: "#F4F4F5", surface: "#FFFFFF" },
  cool:    { bg: "#F8FAFC", bg2: "#F1F5F9", surface: "#FFFFFF" },
};

export const useTweaks = create<TweaksState>()(
  persist(
    (set) => ({
      ...DEFAULTS,
      setTheme: (theme) => set({ theme }),
      setDensity: (density) => set({ density }),
      setFontSize: (fontSizePx) => set({ fontSizePx }),
      setPrimaryColor: (primaryColor) => set({ primaryColor }),
      setSurfaceTint: (surfaceTint) => set({ surfaceTint }),
      reset: () => set({ ...DEFAULTS }),
    }),
    { name: "helix-tweaks", version: 1 },
  ),
);

/** Resolve `theme: "auto"` to the OS preference. */
function resolveTheme(theme: ThemeMode): "light" | "dark" {
  if (theme !== "auto") return theme;
  if (typeof window === "undefined") return "light";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

/**
 * Apply current store values to `<html>` as CSS variables + classes. Call
 * once at app mount (via `ThemeProvider`) and again whenever the store changes.
 */
export function applyTweaksToDocument(state: TweaksState): void {
  if (typeof document === "undefined") return;
  const root = document.documentElement;

  // 1. Dark/light class.
  const resolved = resolveTheme(state.theme);
  root.classList.toggle("dark", resolved === "dark");
  root.dataset.theme = resolved;

  // 2. Font size (drives `:root { font-size }` via --tweak-font-size).
  root.style.setProperty("--tweak-font-size", `${state.fontSizePx}px`);

  // 3. Density multiplier (consumed by .density-padding utility if used).
  root.style.setProperty("--tweak-density", String(DENSITY_MULTIPLIER[state.density]));
  root.dataset.density = state.density;

  // 4. Primary brand color — only in light mode (dark uses its own soft variant).
  if (resolved === "light") {
    root.style.setProperty("--con-brand", state.primaryColor);
    root.style.setProperty("--hx-accent", state.primaryColor);
  } else {
    root.style.removeProperty("--con-brand");
    root.style.removeProperty("--hx-accent");
  }

  // 5. Surface tint (light mode only).
  if (resolved === "light") {
    const tint = SURFACE_TINTS[state.surfaceTint];
    root.style.setProperty("--con-bg", tint.bg);
    root.style.setProperty("--con-bg-2", tint.bg2);
    root.style.setProperty("--con-surface", tint.surface);
  } else {
    root.style.removeProperty("--con-bg");
    root.style.removeProperty("--con-bg-2");
    root.style.removeProperty("--con-surface");
  }
}
