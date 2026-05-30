"use client";

/**
 * /admin/custom-connectors — planned feature.
 *
 * The custom-connector SDK exists in the backend (connectors/custom), but the
 * upload/deploy management UI isn't built yet. This page honestly describes
 * what's planned rather than showing a dead "Coming soon" link or fake data.
 */

import { Wrench, Upload, PackageCheck, ShieldCheck } from "lucide-react";
import { AdminShell } from "@/components/layout";
import { Card, Chip } from "@/components/ui";

export default function CustomConnectorsPage() {
  return (
    <AdminShell
      title="Custom Connectors"
      subtitle="Build, upload, and manage your own source/target connectors via the Helix connector SDK."
      page="Custom Connectors"
      actions={<Chip tone="default">Planned</Chip>}
    >
      <Card padding="lg">
        <div className="flex flex-col items-center text-center py-6 max-w-lg mx-auto">
          <div className="grid place-items-center h-12 w-12 rounded-2xl bg-[var(--con-brand-soft)] text-[var(--con-brand)]">
            <Wrench className="h-5 w-5" />
          </div>
          <h3 className="mt-4 text-[15px] font-semibold text-ink">Bring your own connector</h3>
          <p className="mt-1.5 text-[13px] text-ink-3">
            Helix ships a connector SDK (<span className="font-mono text-[12px]">connectors/custom</span>) so engineers can add
            databases and file stores Helix doesn’t support out of the box. A management surface to upload, version, and
            enable those connectors is on the roadmap.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-2">
          <PlanItem icon={<Upload className="h-4 w-4" />} title="Upload & register" desc="Package a connector and register it for your org." />
          <PlanItem icon={<PackageCheck className="h-4 w-4" />} title="Version & enable" desc="Track versions and toggle availability." />
          <PlanItem icon={<ShieldCheck className="h-4 w-4" />} title="Capability checks" desc="Validate test/discovery/recon support on deploy." />
        </div>

        <p className="mt-5 text-[11.5px] text-ink-4 text-center">
          Today, custom connectors are added in code and appear automatically under
          {" "}<a href="/admin/connectors" className="text-[var(--con-brand)] hover:underline">Connector Management</a>.
        </p>
      </Card>
    </AdminShell>
  );
}

function PlanItem({ icon, title, desc }: { icon: React.ReactNode; title: string; desc: string }) {
  return (
    <div className="rounded-[10px] border border-hx bg-surface p-4">
      <div className="grid place-items-center h-8 w-8 rounded-lg bg-app-2 text-ink-3">{icon}</div>
      <div className="mt-2.5 text-[13px] font-medium text-ink">{title}</div>
      <div className="text-[12px] text-ink-3 mt-0.5">{desc}</div>
    </div>
  );
}
