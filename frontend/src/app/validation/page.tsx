"use client";

/**
 * /validation — Validation Center.
 *
 * Real data sources wired today:
 *   • GET /api/v1/dashboard/stats  → org-wide validation pass-rate (hero)
 *   • GET /api/v1/projects         → whether any projects exist yet
 *
 * Validation rules, runs and recon scores are per-project endpoints
 * (POST/GET /api/v1/projects/{id}/validation-rules, /validation-runs,
 * /recon-runs). There is no org-wide feed for the checks table, the
 * per-category breakdown or the recon-score trend, so those panels render
 * clean empty states here until a project drill-in / aggregate lands.
 */

import { useEffect, useState } from "react";

import { useAuth } from "@/lib/auth-context";
import { fetchDashboardStats, type DashboardStats } from "@/lib/dashboard/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
import { Download, Plus, RefreshCw } from "lucide-react";

import { AppShell } from "@/components/layout";
import { Button, Card, EmptyState, ErrorBanner } from "@/components/ui";

export default function ValidationPage() {
  const { token } = useAuth();
  const [hasProjects, setHasProjects] = useState<boolean | null>(null);
  const [orgStats, setOrgStats] = useState<DashboardStats | null>(null);
  const [loadError, setLoadError] = useState<string>("");

  useEffect(() => {
    // SC-010: auth via the HttpOnly cookie (credentials:"include"); no token gate.
    let cancelled = false;
    fetch(`${API_BASE}/api/v1/projects?limit=1`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : []))
      .then((rows: unknown[]) => { if (!cancelled) setHasProjects(rows.length > 0); })
      .catch((e: unknown) => { if (!cancelled) { setHasProjects(false); setLoadError((e instanceof Error ? e.message : null) ?? "Failed to load projects"); } });
    fetchDashboardStats(token)
      .then((s) => { if (!cancelled) setOrgStats(s); })
      .catch((e: unknown) => { if (!cancelled) { setOrgStats(null); setLoadError((e instanceof Error ? e.message : null) ?? "Failed to load dashboard stats"); } });
    return () => { cancelled = true; };
  }, [token]);

  const realPassRate = orgStats?.validationPassRate;
  const showRealHero = realPassRate !== null && realPassRate !== undefined;

  return (
    <AppShell
      eyebrow="DATA QUALITY · MIGRATION READINESS"
      title="Validation"
      description="Schema integrity, row counts, null checks, duplicates, distribution and business-rule validations across all migrations."
      actions={
        <>
          <Button variant="outline" disabled title="Export coming soon"><Download className="h-3.5 w-3.5" /> Export</Button>
          <Button variant="outline" disabled title="Run all coming soon"><RefreshCw className="h-3.5 w-3.5" /> Run all</Button>
          <Button variant="primary" disabled title="Add validation rules from a project"><Plus className="h-3.5 w-3.5" /> New rule</Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {loadError && <ErrorBanner message={loadError} onDismiss={() => setLoadError("")} />}

        {/* Top: pass rate hero + distribution */}
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_1.4fr] gap-4">
          <Card padding="lg">
            <div className="eyebrow">OVERALL PASS RATE</div>
            <div className="flex items-baseline gap-3 mt-2 min-w-0">
              {/* UI-031 — step the hero number down on narrow viewports so it
                  doesn't overflow its squeezed 1fr column in the grid. */}
              <span className="font-mono tabular-nums text-[40px] sm:text-[48px] lg:text-[56px] font-medium tracking-[-0.03em] leading-none truncate">
                {showRealHero ? (realPassRate ?? 0).toFixed(1) : "—"}
              </span>
              {showRealHero && <span className="text-[24px] sm:text-[28px] text-ink-3 font-normal">%</span>}
              {showRealHero && (
                <span className="ml-auto text-[12px] font-mono text-ink-3">org-wide</span>
              )}
            </div>
            {!showRealHero && (
              <div className="mt-3 text-[12px] text-ink-3">
                No validation results yet. Run a validation rule on a project to populate the org-wide pass rate.
              </div>
            )}
          </Card>

          <Card
            title="Checks by type"
            eyebrow="LAST RUN WINDOW"
            description="Pass / fail / warning breakdown per validation category"
          >
            <EmptyState
              title="No category data yet"
              description="Run a validation rule on a project to populate the per-category breakdown."
            />
          </Card>
        </div>

        {/* Filter & table */}
        <Card padding="md">
          <EmptyState
            title="No validation rules yet"
            description={
              hasProjects === false
                ? "Create a project first, then attach validation rules — their pass / warning / fail results will land here."
                : "Attach validation rules to a project, then runs and their pass / warning / fail results will land here."
            }
          />
        </Card>

        {/* Score trend */}
        <Card
          title="Recon score trend"
          description="Daily reconciliation score across all active projects · last 14 days"
        >
          <EmptyState
            title="No recon runs yet"
            description="Reconciliation runs on a project will chart their daily score here."
          />
        </Card>
      </div>
    </AppShell>
  );
}
