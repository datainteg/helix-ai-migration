"use client";

import { useEffect, useRef, type ReactNode } from "react";

/**
 * Modal — accessible dialog primitive. Implements:
 *  - role="dialog" + aria-modal="true" + labelledby (if title) so screen
 *    readers announce it as a dialog.
 *  - Focus trap: Tab + Shift+Tab cycle within the dialog; closing returns
 *    focus to the trigger element (passed in `returnFocus`, or whatever had
 *    focus before the modal opened).
 *  - Escape to close.
 *  - Backdrop click to close (opt-in via `closeOnBackdrop`).
 *  - Body scroll lock while open.
 *
 * Replaces the ad-hoc `fixed inset-0 bg-black/40` overlays used by sprint
 * "New sprint", "New task", first-admin step modals, and TweaksPanel.
 */
export interface ModalProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  description?: string;
  children: ReactNode;
  /** Element to restore focus to on close. Defaults to document.activeElement at open. */
  returnFocus?: HTMLElement | null;
  closeOnBackdrop?: boolean;
  /** Width preset. */
  width?: "sm" | "md" | "lg";
}

const WIDTH_CLASS: Record<NonNullable<ModalProps["width"]>, string> = {
  sm: "max-w-[420px]",
  md: "max-w-[560px]",
  lg: "max-w-[820px]",
};

export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  returnFocus,
  closeOnBackdrop = true,
  width = "md",
}: ModalProps) {
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const previouslyFocused = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;
    previouslyFocused.current =
      returnFocus ?? (document.activeElement instanceof HTMLElement ? document.activeElement : null);

    // Lock background scroll.
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    // Move focus into the dialog (first focusable element, or container).
    const node = dialogRef.current;
    if (node) {
      const focusable = node.querySelector<HTMLElement>(
        "button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])",
      );
      (focusable ?? node).focus();
    }

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
        return;
      }
      if (e.key !== "Tab" || !dialogRef.current) return;
      const focusables = Array.from(
        dialogRef.current.querySelectorAll<HTMLElement>(
          "button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex='-1'])",
        ),
      ).filter((el) => el.offsetParent !== null);
      if (focusables.length === 0) {
        e.preventDefault();
        return;
      }
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      const active = document.activeElement as HTMLElement | null;
      if (e.shiftKey && active === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && active === last) {
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
  }, [open, onClose, returnFocus]);

  if (!open) return null;

  const titleId = title ? "modal-title" : undefined;
  const descId = description ? "modal-desc" : undefined;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-[2px] px-4"
      onClick={(e) => {
        if (closeOnBackdrop && e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descId}
        tabIndex={-1}
        className={`w-full ${WIDTH_CLASS[width]} bg-surface border border-hx rounded-[10px] shadow-xl outline-none`}
      >
        {(title || description) && (
          <div className="px-5 pt-4 pb-3 border-b border-hx">
            {title && (
              <h2 id={titleId} className="text-[15px] font-medium text-ink m-0">
                {title}
              </h2>
            )}
            {description && (
              <p id={descId} className="mt-1 text-[12.5px] text-ink-3">
                {description}
              </p>
            )}
          </div>
        )}
        <div className="px-5 py-4">{children}</div>
      </div>
    </div>
  );
}
