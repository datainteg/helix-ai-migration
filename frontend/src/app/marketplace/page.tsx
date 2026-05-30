"use client";

/**
 * /marketplace — community plugin catalog.
 *
 * Browse-only. Each entry carries an explicit install_command operators run
 * themselves so the trust boundary stays clear (no auto-install from a UI).
 */

import { useEffect, useState } from "react";
import { Package, Puzzle, ShieldAlert, BookOpen, Bot, Filter } from "lucide-react";

import { AppShell } from "@/components/layout";
import { Button, Card, Chip, EmptyState, ErrorBanner, LoadingState } from "@/components/ui";
import { useAuth } from "@/lib/auth-context";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface Entry {
  id: string;
  name: string;
  kind: "connector" | "agent" | "validator" | "recipe";
  source_type?: string | null;
  target_type?: string | null;
  description: string;
  license: string;
  author: string;
  homepage: string;
  pip_package?: string | null;
  install_command: string;
  risk: "low" | "medium" | "high";
}

const KIND_ICON = {
  connector: Puzzle,
  agent: Bot,
  validator: ShieldAlert,
  recipe: BookOpen,
};

export default function MarketplacePage() {
  const { token } = useAuth();
  const [items, setItems] = useState<Entry[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>("all");
  const [loadError, setLoadError] = useState<string>("");

  useEffect(() => {
    // SC-010: auth via the HttpOnly cookie (credentials:"include"); no token gate.
    fetch(`${API_BASE}/api/v1/marketplace`, { credentials: "include" })
      .then((r) => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
      .then((data: Entry[]) => setItems(data))
      .catch((e: unknown) => { setItems([]); setLoadError((e instanceof Error ? e.message : null) ?? "Failed to load marketplace"); })
      .finally(() => setLoading(false));
  }, []);

  const filtered = filter === "all" ? items : items.filter((e) => e.kind === filter);

  return (
    <AppShell
      eyebrow="EXTEND HELIX"
      title="Plugin marketplace"
      description="Community-contributed connectors, agents, validators, and recipes."
      crumbs={["Marketplace"]}
    >
      {loadError && <ErrorBanner message={loadError} onDismiss={() => setLoadError("")} />}
      <div className="flex flex-wrap gap-2 mb-4 items-center">
        <Filter className="h-3.5 w-3.5 text-ink-4" />
        {[
          { id: "all", label: "All" },
          { id: "connector", label: "Connectors" },
          { id: "agent", label: "Agents" },
          { id: "validator", label: "Validators" },
          { id: "recipe", label: "Recipes" },
        ].map((f) => (
          <button
            key={f.id}
            onClick={() => setFilter(f.id)}
            className={`px-3 h-7 rounded-[7px] text-[12.5px] border ${
              filter === f.id
                ? "border-ink bg-app-2 font-medium"
                : "border-hx bg-surface text-ink-2 hover:bg-app-2"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>
      {loading ? (
        <LoadingState label="Loading marketplace…" />
      ) : filtered.length === 0 ? (
        <EmptyState title="Nothing to show" description="No marketplace entries match this filter." />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {filtered.map((e) => {
            const Icon = KIND_ICON[e.kind] ?? Package;
            return (
              <Card key={e.id} bodyClassName="p-4 flex flex-col gap-2.5">
                <div className="flex items-center gap-2.5">
                  <Icon className="h-4 w-4 text-[var(--con-brand)]" />
                  <span className="text-[13px] font-medium">{e.name}</span>
                </div>
                <p className="text-[12px] text-ink-3 leading-relaxed line-clamp-4">{e.description}</p>
                <div className="flex flex-wrap gap-1.5 text-[10.5px]">
                  <Chip tone="default">{e.kind}</Chip>
                  <Chip tone={e.risk === "high" ? "err" : e.risk === "medium" ? "amber" : "ok"}>risk: {e.risk}</Chip>
                  <Chip tone="default">{e.license}</Chip>
                </div>
                <pre className="mt-1 text-[11px] font-mono p-2 rounded-[6px] bg-app-2 border border-hx overflow-x-auto">{e.install_command}</pre>
                <div className="flex gap-2 mt-1">
                  <a href={e.homepage} target="_blank" rel="noreferrer noopener">
                    <Button variant="outline" size="sm">Docs</Button>
                  </a>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </AppShell>
  );
}
