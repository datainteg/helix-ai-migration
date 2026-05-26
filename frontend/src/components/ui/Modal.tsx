"use client";

import { useCallback, useId, useRef, type ReactNode } from "react";
import { useFocusTrap } from "@/lib/use-focus-trap";

/**
 * Modal — accessible dialog primitive. Implements:
 *  - role="dialog" + aria-modal="true" + labelledby (if title) so screen
 *    readers announce it as a dialog.
 *  - Focus trap + Escape close + body scroll lock + focus restore: shared
 *    with the TweaksPanel drawer via the `useFocusTrap` hook (canonical
 *    implementation in `frontend/src/lib/use-focus-trap.ts`).
 *  - Backdrop click to close (opt-in via `closeOnBackdrop`). Checks the
 *    mousedown target to avoid the drag-out-of-dialog close trap.
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
  returnFocus: _returnFocus,
  closeOnBackdrop = true,
  width = "md",
}: ModalProps) {
  const dialogRef = useRef<HTMLDivElement | null>(null);
  // Track the element we mousedowned on so a drag-out-and-release on the
  // backdrop does NOT count as a backdrop click. The standard pattern checks
  // mousedown target equality.
  const mouseDownTarget = useRef<EventTarget | null>(null);

  const onEscape = useCallback(() => onClose(), [onClose]);
  useFocusTrap(dialogRef, open, onEscape);

  // useId ensures unique ids even when multiple modals mount concurrently
  // (e.g. a nested confirmation on top of a primary form modal).
  const uid = useId();
  const titleId = title ? `${uid}-title` : undefined;
  const descId = description ? `${uid}-desc` : undefined;

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 motion-safe:backdrop-blur-[2px] px-4"
      onMouseDown={(e) => { mouseDownTarget.current = e.target; }}
      onClick={(e) => {
        if (closeOnBackdrop && e.target === e.currentTarget && mouseDownTarget.current === e.currentTarget) {
          onClose();
        }
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
