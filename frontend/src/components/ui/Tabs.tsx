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
}

/**
 * Segmented tabs. Two variants:
 * - "pill"     : a single grouped tab control (good in toolbars)
 * - "underline": a row of inline tabs with a bottom rule (good as section headers)
 */
export function Tabs({ tabs, value, onChange, variant = "pill", className }: TabsProps) {
  if (variant === "underline") {
    return (
      <div className={cn("flex border-b border-hx -mb-px", className)}>
        {tabs.map((t) => {
          const active = t.id === value;
          return (
            <button
              key={t.id}
              type="button"
              onClick={() => onChange(t.id)}
              className={cn(
                "px-3.5 py-2.5 text-[12.5px] font-medium border-b-[1.5px] -mb-px transition-colors",
                "inline-flex items-center gap-1.5",
                active
                  ? "text-ink border-ink"
                  : "text-ink-3 border-transparent hover:text-ink-2"
              )}
            >
              {t.label}
              {t.count !== undefined && (
                <span className="font-mono text-[11px] text-ink-4">{t.count}</span>
              )}
            </button>
          );
        })}
      </div>
    );
  }
  // pill variant
  return (
    <div className={cn("inline-flex p-[3px] bg-app-2 rounded-[8px] gap-0.5", className)}>
      {tabs.map((t) => {
        const active = t.id === value;
        return (
          <button
            key={t.id}
            type="button"
            onClick={() => onChange(t.id)}
            className={cn(
              "px-2.5 py-[5px] text-[12px] font-medium rounded-[6px] transition-colors",
              "inline-flex items-center gap-1.5",
              active
                ? "bg-surface text-ink shadow-xs"
                : "text-ink-3 hover:text-ink-2"
            )}
          >
            {t.label}
            {t.count !== undefined && (
              <span className="font-mono text-[10.5px] text-ink-4">{t.count}</span>
            )}
          </button>
        );
      })}
    </div>
  );
}
