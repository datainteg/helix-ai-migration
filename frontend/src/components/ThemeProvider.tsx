"use client";

/**
 * Mounts the theme/tweaks store: applies values to the document on first
 * paint and whenever the store changes. Place once near the app root.
 *
 * When a user is authenticated, also:
 *  - On mount: GET /users/me/preferences → hydrate store (so a tweak made
 *    on device A shows up on device B without local-storage carryover).
 *  - On change: debounced PATCH /users/me/preferences (500ms).
 *
 * Logged-out users continue to use localStorage only — no server round-trip.
 */

import { useEffect, useRef } from "react";

import { useAuth } from "@/lib/auth-context";
import {
  applyTweaksToDocument,
  snapshotTweaks,
  TweaksSnapshot,
  useTweaks,
} from "@/lib/theme-store";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const SYNC_DEBOUNCE_MS = 500;

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const state = useTweaks();
  const { token } = useAuth();
  const hydratedRef = useRef(false);
  const lastSyncedRef = useRef<string>("");
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Apply to document on first paint + every store change.
  useEffect(() => {
    applyTweaksToDocument(state);
  }, [state]);

  // Re-apply when OS theme changes (only relevant when theme="auto").
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

  // One-shot hydrate from server on first authenticated render.
  useEffect(() => {
    if (!token || hydratedRef.current) return;
    hydratedRef.current = true;
    fetch(`${API_BASE}/api/v1/users/me/preferences`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((prefs: Partial<TweaksSnapshot> | null) => {
        if (prefs && typeof prefs === "object" && Object.keys(prefs).length > 0) {
          useTweaks.getState().hydrateFromServer(prefs);
          // Remember what we just received so we don't echo it right back.
          lastSyncedRef.current = JSON.stringify(prefs);
        }
      })
      .catch(() => {});
  }, [token]);

  // Debounced sync of local changes to the server.
  useEffect(() => {
    if (!token || !hydratedRef.current) return;
    const snap = snapshotTweaks(state);
    const serialized = JSON.stringify(snap);
    if (serialized === lastSyncedRef.current) return;

    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      lastSyncedRef.current = serialized;
      fetch(`${API_BASE}/api/v1/users/me/preferences`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ preferences: snap }),
      }).catch(() => {});
    }, SYNC_DEBOUNCE_MS);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [state, token]);

  // Reset hydration flag on logout so re-login re-hydrates.
  useEffect(() => {
    if (!token) {
      hydratedRef.current = false;
      lastSyncedRef.current = "";
    }
  }, [token]);

  return <>{children}</>;
}
