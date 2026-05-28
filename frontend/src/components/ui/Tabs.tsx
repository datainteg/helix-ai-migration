"use client";

import { useId, useRef, type KeyboardEvent } from "react";
import { cn } from "@/lib/utils";

interface Tab {
  id: string;
  label: React.ReactNode;
  count?: number;
}

interface TabsProps {
  tabs: Tab[];
  value: string;
  onChange: (id: string) => void;
  variant?: "pill" | "underline";
  className?: string;
  /** Optional id used to wire aria-controls onto the visible panel. Consumers
   * who render the panel themselves should pass the panel's id so screen
   * readers can announce the tab-panel relationship. */
  panelId?: string;
  /** Accessible name for the tablist. */
  label?: string;
}

/**
 * Segmented tabs. Two variants:
 * - "pill"     : a single grouped tab control (good in toolbars)
 * - "underline": a row of inline tabs with a bottom rule (good as section headers)
 *
 * Wires `role="tablist"` + `role="tab"` + `aria-selected` + arrow-key nav so
 * the control is announced as tabs by screen readers and obeys WAI-ARIA APG
 * tab pattern. Roving tabindex pattern: only the active tab is in the tab
 * order; arrow keys move between tabs.
 */
export function Tabs({ tabs, value, onChange, variant = "pill", className, panelId, label }: TabsProps) {
  const autoId = useId();
  const tablistId = `tablist-${autoId}`;
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);

  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const i = tabs.findIndex((t) => t.id === value);
    if (i < 0) return;
    let next = i;
    if (e.key === "ArrowRight" || e.key === "ArrowDown") next = (i + 1) % tabs.length;
    else if (e.key === "ArrowLeft" || e.key === "ArrowUp") next = (i - 1 + tabs.length) % tabs.length;
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = tabs.length - 1;
    else return;
    e.preventDefault();
    const nextTab = tabs[next];
    if (nextTab) {
      onChange(nextTab.id);
      tabRefs.current[next]?.focus();
    }
  };

  const tabId = (id: string) => `${tablistId}-tab-${id}`;

  if (variant === "underline") {
    return (
      <div
        role="tablist"
        id={tablistId}
        aria-label={label}
        onKeyDown={onKey}
        className={cn("flex border-b border-hx -mb-px", className)}
      >
        {tabs.map((t, idx) => {
          const active = t.id === value;
          return (
            <button
              key={t.id}
              ref={(el) => { tabRefs.current[idx] = el; }}
              type="button"
              role="tab"
              id={tabId(t.id)}
              aria-selected={active}
              aria-controls={panelId}
              tabIndex={active ? 0 : -1}
              onClick={() => onChange(t.id)}
              className={cn(
                "px-3.5 py-2.5 text-[12.5px] font-medium border-b-[1.5px] -mb-px transition-colors",
                "inline-flex items-center gap-1.5 focus-ring",
                active
                  ? "text-ink border-ink"
                  : "text-ink-3 border-transparent hover:text-ink-2"
              )}
            >
              {t.label}
              {t.count !== undefined && (
                <span className="font-mono text-[11px] text-ink-3">{t.count}</span>
              )}
            </button>
          );
        })}
      </div>
    );
  }
  // pill variant
  return (
    <div
      role="tablist"
      id={tablistId}
      aria-label={label}
      onKeyDown={onKey}
      className={cn("inline-flex p-[3px] bg-app-2 rounded-[8px] gap-0.5", className)}
    >
      {tabs.map((t, idx) => {
        const active = t.id === value;
        return (
          <button
            key={t.id}
            ref={(el) => { tabRefs.current[idx] = el; }}
            type="button"
            role="tab"
            id={tabId(t.id)}
            aria-selected={active}
            aria-controls={panelId}
            tabIndex={active ? 0 : -1}
            onClick={() => onChange(t.id)}
            className={cn(
              "px-2.5 py-[5px] text-[12px] font-medium rounded-[6px] transition-colors",
              "inline-flex items-center gap-1.5 focus-ring",
              active
                ? "bg-surface text-ink shadow-xs"
                : "text-ink-3 hover:text-ink-2"
            )}
          >
            {t.label}
            {t.count !== undefined && (
              <span className="font-mono text-[11px] text-ink-3">{t.count}</span>
            )}
          </button>
        );
      })}
    </div>
  );
}
