import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  FolderKanban,
  Workflow,
  ShieldCheck,
  GitCompareArrows,
  TerminalSquare,
  Plug,
  KanbanSquare,
  Settings,
} from "lucide-react";

const ITEMS = [
  { to: "/demo",                label: "Dashboard",           icon: LayoutDashboard,    end: true  },
  { to: "/demo/project",        label: "Project workspace",   icon: FolderKanban,       end: false },
  { to: "/demo/agents",         label: "Agent workflow",      icon: Workflow,           end: false },
  { to: "/demo/validation",     label: "Validation center",   icon: ShieldCheck,        end: false },
  { to: "/demo/recon",          label: "Recon dashboard",     icon: GitCompareArrows,   end: false },
  { to: "/demo/developer",      label: "Developer workspace", icon: TerminalSquare,     end: false },
  { to: "/demo/connectors",     label: "Connectors",          icon: Plug,               end: false },
  { to: "/demo/sprint-mapping", label: "Sprint mapping",      icon: KanbanSquare,       end: false },
  { to: "/demo/admin",          label: "Admin panel",         icon: Settings,           end: false },
];

export function DemoSidebar() {
  return (
    <>
      {/* Desktop vertical sidebar */}
      <aside className="hidden md:block w-[240px] shrink-0">
        <div className="sticky top-20">
          <div className="eyebrow mb-3 px-2">Demo screens</div>
          <nav className="flex flex-col gap-0.5">
            {ITEMS.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  className={({ isActive }) =>
                    "flex items-center gap-2.5 px-3 py-2 rounded-md text-[13.5px] font-medium transition-colors focus-ring " +
                    (isActive
                      ? "bg-brand-50 text-brand-700"
                      : "text-ink-3 hover:text-ink hover:bg-zinc-100/70")
                  }
                >
                  <Icon className="h-4 w-4 shrink-0" />
                  <span className="truncate">{item.label}</span>
                </NavLink>
              );
            })}
          </nav>
        </div>
      </aside>

      {/* Mobile horizontal nav */}
      <div className="md:hidden -mx-6 px-6 mb-4 overflow-x-auto">
        <nav className="flex gap-1 pb-2 min-w-max">
          {ITEMS.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  "flex items-center gap-1.5 px-3 py-1.5 rounded-md text-[12.5px] font-medium whitespace-nowrap focus-ring " +
                  (isActive
                    ? "bg-brand-50 text-brand-700"
                    : "text-ink-3 hover:text-ink bg-zinc-100/60")
                }
              >
                <Icon className="h-3.5 w-3.5" />
                {item.label}
              </NavLink>
            );
          })}
        </nav>
      </div>
    </>
  );
}
