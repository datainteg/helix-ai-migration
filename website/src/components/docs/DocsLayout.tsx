import { ReactNode } from "react";
import { ChevronDown } from "lucide-react";

import { DocsSidebar } from "./DocsSidebar";

interface DocsLayoutProps {
  children: ReactNode;
}

export function DocsLayout({ children }: DocsLayoutProps) {
  return (
    <div className="container-tight py-8 lg:py-12">
      <div className="lg:hidden mb-6">
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

      <div className="flex gap-10">
        <DocsSidebar />
        <div className="flex-1 min-w-0">{children}</div>
      </div>
    </div>
  );
}
