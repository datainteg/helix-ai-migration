"use client";

/**
 * /admin/import-export — planned feature, with the export paths that DO exist.
 *
 * Full project/plan/config import-export isn't built yet, so the page is honest
 * about that — but it surfaces the real export endpoints already available
 * (usage CSV, audit-log CSV/PDF) so the tile lands somewhere useful.
 */

import { Upload, Download, FileText, FileSpreadsheet } from "lucide-react";
import { AdminShell } from "@/components/layout";
import { Card, Button, Chip } from "@/components/ui";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

async function download(path: string, filename: string) {
  const res = await fetch(`${API_BASE}${path}`, { credentials: "include" });
  if (!res.ok) return;
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click(); a.remove();
  URL.revokeObjectURL(url);
}

export default function ImportExportPage() {
  return (
    <AdminShell
      title="Import / Export"
      subtitle="Move projects, plans, and configurations between Helix instances. Available exports are listed below."
      page="Import / Export"
    >
      <Card title="Available exports" description="These data exports are available today.">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <ExportItem
            icon={<FileSpreadsheet className="h-4 w-4" />}
            title="LLM usage (CSV)"
            desc="Per-agent token + cost usage for the last 30 days."
            onClick={() => download("/api/v1/usage/llm/export.csv?days=30", "helix-usage-30d.csv")}
          />
          <ExportItem
            icon={<FileText className="h-4 w-4" />}
            title="Audit logs (CSV)"
            desc="Security and activity events."
            onClick={() => download("/api/v1/audit-logs/export/csv", "helix-audit-logs.csv")}
          />
        </div>
      </Card>

      <Card title="Project import / export" actions={<Chip tone="default">Planned</Chip>}>
        <div className="flex flex-col items-center text-center py-5 max-w-lg mx-auto">
          <div className="grid place-items-center h-12 w-12 rounded-2xl bg-[var(--con-brand-soft)] text-[var(--con-brand)]">
            <Upload className="h-5 w-5" />
          </div>
          <h3 className="mt-4 text-[15px] font-semibold text-ink">Portable projects & configs</h3>
          <p className="mt-1.5 text-[13px] text-ink-3">
            Exporting a full project (its mappings, plans, connectors, and settings) as a portable bundle and importing it
            into another Helix instance is on the roadmap. For now, use the data exports above and the per-feature
            settings pages.
          </p>
          <div className="mt-4 flex gap-2">
            <Button variant="outline" disabled><Download className="h-3.5 w-3.5" /> Export project</Button>
            <Button variant="outline" disabled><Upload className="h-3.5 w-3.5" /> Import bundle</Button>
          </div>
        </div>
      </Card>
    </AdminShell>
  );
}

function ExportItem({ icon, title, desc, onClick }: { icon: React.ReactNode; title: string; desc: string; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} className="text-left rounded-[10px] border border-hx bg-surface p-4 hover:bg-surface-hi hover:border-hx-2 transition-colors">
      <div className="flex items-start gap-3">
        <div className="grid place-items-center h-9 w-9 rounded-lg bg-app-2 text-ink-3 flex-shrink-0">{icon}</div>
        <div className="min-w-0">
          <div className="text-[13px] font-medium text-ink flex items-center gap-1.5">{title} <Download className="h-3 w-3 text-ink-4" /></div>
          <div className="text-[12px] text-ink-3 mt-0.5">{desc}</div>
        </div>
      </div>
    </button>
  );
}
