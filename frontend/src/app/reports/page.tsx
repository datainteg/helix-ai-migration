"use client";

/**
 * /reports — placeholder.
 *
 * Report generation isn't wired yet; this stub keeps the route navigable.
 * Replace with the real report library once `/api/v1/reports` lands.
 */

import Link from "next/link";
import { FileText } from "lucide-react";
import { AppShell } from "@/components/layout";
import { Button, Card, EmptyState } from "@/components/ui";

export default function ReportsPage() {
  return (
    <AppShell
      eyebrow="DELIVERABLES"
      title="Reports"
      description="Migration plans, validation outcomes, recon summaries, and audit-ready deliverables."
      crumbs={[{ label: "Reports" }]}
    >
      <Card>
        <EmptyState
          icon={<FileText className="h-5 w-5" />}
          title="Report library is coming soon"
          description="Generated migration plans, validation outcomes, and recon summaries will be downloadable from here once the report service ships."
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
