"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { AppShell } from "./AppShell";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { cn } from "@/lib/utils";

interface Props {
  children: React.ReactNode;
  projectId: string;
  projectName: string;
  projectStatus?: string;
  subtitle?: string;
  actions?: React.ReactNode;
}

const TABS = [
  { label: "Overview", suffix: "" },
  { label: "Requirements", suffix: "/requirements" },
  { label: "Agents", suffix: "/agents" },
  { label: "Migration", suffix: "/migration" },
  { label: "Source & Target", suffix: "/source-target" },
  { label: "Validation", suffix: "/validation" },
  { label: "Recon", suffix: "/recon" },
  { label: "Cutover", suffix: "/cutover" },
  { label: "Developer Workspace", suffix: "/developer-workspace" },
  { label: "Compliance", suffix: "/compliance" },
  { label: "Reports", suffix: "/reports" },
  { label: "Approvals", suffix: "/approvals" },
  { label: "Timeline", suffix: "/timeline" },
];

export function ProjectShell({ children, projectId, projectName, projectStatus, subtitle, actions }: Props) {
  const pathname = usePathname() || "";
  const base = `/projects/${projectId}`;
  return (
    <AppShell
      title={projectName}
      subtitle={subtitle}
      crumbs={[{ label: "Projects", href: "/projects" }, { label: projectName }]}
      actions={
        <div className="flex items-center gap-3">
          {projectStatus && <StatusBadge status={projectStatus} />}
          {actions}
        </div>
      }
    >
      <div className="border-b border-hx -mx-6 sm:-mx-8 px-6 sm:px-8 mb-6 overflow-x-auto">
        <nav className="flex gap-1 min-w-max">
          {TABS.map((tab) => {
            const href = `${base}${tab.suffix}`;
            const active = tab.suffix === "" ? pathname === base : pathname.startsWith(href);
            return (
              <Link
                key={tab.label}
                href={href}
                className={cn(
                  "px-3.5 py-2.5 text-[13px] border-b-2 transition-colors -mb-px",
                  active
                    ? "border-helix-500 text-helix-700 font-medium"
                    : "border-transparent text-ink-3 hover:text-ink-2"
                )}
              >
                {tab.label}
              </Link>
            );
          })}
        </nav>
      </div>
      <div className="space-y-6">{children}</div>
    </AppShell>
  );
}
