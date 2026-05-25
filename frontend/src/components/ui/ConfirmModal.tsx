"use client";

import { useEffect, useRef } from "react";
import { Modal } from "./Modal";
import { Button } from "./Button";

interface ConfirmModalProps {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void | Promise<void>;
  title: string;
  description?: string;
  /** Label for the confirm button. Defaults to "Confirm". */
  confirmLabel?: string;
  /** Label for the cancel button. Defaults to "Cancel". */
  cancelLabel?: string;
  /** Use the danger variant on the confirm button (red border, error text). */
  destructive?: boolean;
  /** Shown while the confirm action is in-flight; disables both buttons. */
  busy?: boolean;
}

/**
 * Styled replacement for `window.confirm()`. Built on the Modal primitive so
 * it inherits focus trap, Escape close, body-scroll lock, and focus restore.
 * Focus lands on the cancel button to avoid accidental destructive actions
 * when a user hits Enter.
 */
export function ConfirmModal({
  open,
  onClose,
  onConfirm,
  title,
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  destructive = false,
  busy = false,
}: ConfirmModalProps) {
  const cancelRef = useRef<HTMLButtonElement | null>(null);

  // Move focus to Cancel on open so Enter does NOT immediately confirm.
  useEffect(() => {
    if (open) {
      const t = setTimeout(() => cancelRef.current?.focus(), 0);
      return () => clearTimeout(t);
    }
  }, [open]);

  return (
    <Modal
      open={open}
      onClose={busy ? () => {} : onClose}
      title={title}
      description={description}
      width="sm"
      closeOnBackdrop={!busy}
    >
      <div className="flex justify-end gap-2 mt-2">
        <Button
          ref={cancelRef}
          type="button"
          variant="outline"
          onClick={onClose}
          disabled={busy}
        >
          {cancelLabel}
        </Button>
        <Button
          type="button"
          variant={destructive ? "danger" : "primary"}
          onClick={() => void onConfirm()}
          loading={busy}
        >
          {confirmLabel}
        </Button>
      </div>
    </Modal>
  );
}
