"use client";

/**
 * Mounts the theme/tweaks store: applies values to the document on first
 * paint and whenever the store changes. Place once near the app root.
 */

import { useEffect } from "react";

import { applyTweaksToDocument, useTweaks } from "@/lib/theme-store";

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  // Subscribe to the full state so applyTweaksToDocument runs on every change.
  const state = useTweaks();

  useEffect(() => {
    applyTweaksToDocument(state);
  }, [state]);

  // Also re-apply when the OS theme changes (only relevant when theme="auto").
  useEffect(() => {
    if (typeof window === "undefined") return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => {
      if (useTweaks.getState().theme === "auto") {
        applyTweaksToDocument(useTweaks.getState());
      }
    };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  return <>{children}</>;
}
