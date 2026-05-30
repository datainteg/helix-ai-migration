"use client";

import { GitCompareArrows } from "lucide-react";
import { AppShell } from "@/components/layout";
import { Card, EmptyState } from "@/components/ui";

export default function ReconciliationPage() {
  return (
    <AppShell
      title="Reconciliation Center"
      subtitle="Compare source and target outcomes with row-level reconciliation insights and anomaly analysis."
      crumbs={[{ label: "Reconciliation" }]}
    >
      <Card>
        <EmptyState
          icon={<GitCompareArrows className="h-5 w-5" />}
          title="No reconciliation runs yet"
          description="Run reconciliation from a project to compare source and target outcomes here."
        />
      </Card>
    </AppShell>
  );
}
