import { ReactNode } from "react";
import { ChevronDown } from "lucide-react";

import { DocsSidebar } from "./DocsSidebar";

interface DocsLayoutProps {
  children: ReactNode;
}

export function DocsLayout({ children }: DocsLayoutProps) {
  return (
    <div className="container-tight py-8 md:py-12">
      {/* Mobile + small-tablet accordion (below md) */}
      <div className="md:hidden mb-6">
        <details className="rounded-lg border border-zinc-200 bg-surface group">
          <summary className="flex items-center justify-between gap-2 px-4 py-3 cursor-pointer text-[13.5px] font-medium text-ink list-none focus-ring rounded-lg">
            <span>Browse docs</span>
            <ChevronDown
              className="h-4 w-4 text-ink-3 transition-transform group-open:rotate-180"
              aria-hidden="true"
            />
          </summary>
          <div className="px-2 pb-4 pt-1">
            <DocsSidebar className="bg-surface px-2 py-2 max-h-[60vh] overflow-y-auto" />
          </div>
        </details>
      </div>

      {/* Tablet + desktop column (md and up) */}
      <div className="flex gap-8 lg:gap-10">
        <DocsSidebar className="hidden md:block bg-surface border-r border-zinc-200 px-4 py-6 sticky top-16 self-start max-h-[calc(100vh-4rem)] overflow-y-auto w-[240px] lg:w-[280px] shrink-0" />
        <div className="flex-1 min-w-0">{children}</div>
      </div>
    </div>
  );
}
