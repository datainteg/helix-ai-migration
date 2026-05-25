import { ReactNode } from "react";
import { Link } from "react-router-dom";
import { DemoSidebar } from "./DemoSidebar";

interface DemoShellProps {
  title: string;
  description?: string;
  children: ReactNode;
}

export function DemoShell({ title, description, children }: DemoShellProps) {
  return (
    <div className="min-h-[calc(100vh-4rem)]">
      {/* Demo banner */}
      <div className="bg-amber-50 border-b border-amber-200 px-6 py-2 text-[12px] text-amber-900 text-center">
        Demo data — interactive walkthrough.{" "}
        <Link to="/docs" className="underline font-medium hover:text-amber-950">
          Read docs
        </Link>{" "}
        to see the real product.
      </div>

      <div className="container-tight py-6 md:py-8">
        <div className="md:flex md:gap-8">
          <DemoSidebar />
          <div className="flex-1 min-w-0">
            <header className="mb-6">
              <h1 className="text-[22px] md:text-[26px] font-semibold tracking-tight text-ink">
                {title}
              </h1>
              {description && (
                <p className="text-[13.5px] text-ink-3 mt-1.5 leading-relaxed max-w-3xl">
                  {description}
                </p>
              )}
            </header>
            {children}
          </div>
        </div>
      </div>
    </div>
  );
}
