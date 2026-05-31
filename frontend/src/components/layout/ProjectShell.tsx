"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Play } from "lucide-react";
import { AppShell } from "./AppShell";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Button } from "@/components/ui";
import { useAuth } from "@/lib/auth-context";
import { cn } from "@/lib/utils";

interface Props {
  children: React.ReactNode;
  projectId: string;
  projectName: string;
  projectStatus?: string;
  subtitle?: string;
  actions?: React.ReactNode;
  /** When true, the Start Workflow CTA is disabled (project on operational hold). */
  onHold?: boolean;
}

// Migration is folded into Workflows (single canonical run UI); the legacy
// /migration route redirects to /agents.
const TABS = [
  { label: "Overview", suffix: "" },
  { label: "Requirements", suffix: "/requirements" },
  { label: "Source & Target", suffix: "/source-target" },
  { label: "Workflows", suffix: "/agents" },
  { label: "Validation", suffix: "/validation" },
  { label: "Recon", suffix: "/recon" },
  { label: "Cutover", suffix: "/cutover" },
  { label: "Developer Workspace", suffix: "/developer-workspace" },
  { label: "Compliance", suffix: "/compliance" },
  { label: "Reports", suffix: "/reports" },
  { label: "Approvals", suffix: "/approvals" },
  { label: "Timeline", suffix: "/timeline" },
];

export function ProjectShell({ children, projectId, projectName, projectStatus, subtitle, actions, onHold }: Props) {
  const pathname = usePathname() || "";
  const { can } = useAuth();
  const base = `/projects/${projectId}`;
  // Persistent Start-Workflow CTA across every project tab. Opens the Run modal
  // on the Workflows tab via ?run=new. Gated by project:write; disabled on hold.
  const canStart = can("project:write");
  return (
    <AppShell
      title={projectName}
      subtitle={subtitle}
      crumbs={[{ label: "Projects", href: "/projects" }, { label: projectName }]}
      actions={
        <div className="flex items-center gap-3">
          {projectStatus && <StatusBadge status={projectStatus} />}
          {actions}
          {canStart && (
            onHold ? (
              <Button variant="outline" disabled title="Project is on hold — resume it to start a workflow">
                <Play className="h-4 w-4" /> Start Workflow
              </Button>
            ) : (
              <Link href={`${base}/agents?run=new`}>
                <Button><Play className="h-4 w-4" /> Start Workflow</Button>
              </Link>
            )
          )}
        </div>
      }
    >
      <div className="sticky top-11 z-10 -mx-6 sm:-mx-8 px-6 sm:px-8 mb-6 border-b border-hx bg-app/85 backdrop-blur supports-[backdrop-filter]:bg-app/70 overflow-x-auto">
        <nav className="flex gap-0.5 min-w-max">
          {TABS.map((tab) => {
            const href = `${base}${tab.suffix}`;
            const active = tab.suffix === "" ? pathname === base : pathname.startsWith(href);
            return (
              <Link
                key={tab.label}
                href={href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "relative px-3 py-2.5 text-[13px] rounded-t-md whitespace-nowrap transition-colors",
                  active
                    ? "text-helix-700 font-medium"
                    : "text-ink-3 hover:text-ink-1 hover:bg-app-2"
                )}
              >
                {tab.label}
                {active && <span className="absolute left-2.5 right-2.5 -bottom-px h-0.5 rounded-full bg-helix-500" />}
              </Link>
            );
          })}
        </nav>
      </div>
      <div className="space-y-6">{children}</div>
    </AppShell>
  );
}
