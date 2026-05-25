"use client";

import { useEffect, useRef } from "react";

/**
 * useFocusTrap — keep focus inside `containerRef` while `active` is true.
 *
 * Behaviour:
 *  - Stores the previously focused element on activate; restores it on
 *    deactivate.
 *  - Moves focus to the first focusable child (or the container) on activate.
 *  - Tab + Shift+Tab wrap within the container.
 *  - Escape calls `onEscape` if provided.
 *  - Locks body scroll while active so background content cannot accept
 *    pointer input behind the dialog.
 *
 * Use this for ad-hoc dialogs/drawers where the Modal primitive does not fit
 * (slide-in drawers, large dialogs that own their own chrome).
 */
export function useFocusTrap(
  containerRef: React.RefObject<HTMLElement | null>,
  active: boolean,
  onEscape?: () => void,
) {
  const previouslyFocused = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!active) return;
    previouslyFocused.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;

    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const node = containerRef.current;
    if (node) {
      const focusable = node.querySelector<HTMLElement>(
        "button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])",
      );
      (focusable ?? node).focus();
    }

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && onEscape) {
        e.preventDefault();
        onEscape();
        return;
      }
      if (e.key !== "Tab" || !containerRef.current) return;
      const focusables = Array.from(
        containerRef.current.querySelectorAll<HTMLElement>(
          "button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex='-1'])",
        ),
      ).filter((el) => el.offsetParent !== null);
      if (!focusables.length) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      const activeEl = document.activeElement as HTMLElement | null;
      if (e.shiftKey && activeEl === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && activeEl === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = prevOverflow;
      document.removeEventListener("keydown", onKey);
      previouslyFocused.current?.focus?.();
    };
  }, [active, onEscape, containerRef]);
}
