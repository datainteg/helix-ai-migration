"use client";

/**
 * /templates — placeholder.
 *
 * Migration-template catalog isn't built yet; this stub keeps the route
 * navigable. Replace with the real template browser once
 * `/api/v1/templates` lands.
 */

import Link from "next/link";
import { LayoutTemplate } from "lucide-react";
import { AppShell } from "@/components/layout";
import { Button, Card, EmptyState } from "@/components/ui";

export default function TemplatesPage() {
  return (
    <AppShell
      eyebrow="PATTERNS"
      title="Migration Templates"
      description="Pre-built templates with mappings, validation suites, and recon checklists."
      crumbs={[{ label: "Templates" }]}
    >
      <Card>
        <EmptyState
          icon={<LayoutTemplate className="h-5 w-5" />}
          title="Template catalog is coming soon"
          description="Reusable Oracle, SAS, SQL Server, and DataStage migration templates will be browsable from here once the template service ships."
          action={
            <div className="flex items-center gap-2">
              <Link href="/dashboard">
                <Button variant="outline">Back to Dashboard</Button>
              </Link>
              {/* UI-042 — give the coming-soon page a roadmap escape hatch. */}
              <a
                href="https://github.com/datainteg/helix-ai-migration/issues"
                target="_blank"
                rel="noopener noreferrer"
              >
                <Button variant="ghost">Track on GitHub</Button>
              </a>
            </div>
          }
        />
      </Card>
    </AppShell>
  );
}
