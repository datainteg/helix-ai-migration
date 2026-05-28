"use client";

/**
 * /files — placeholder.
 *
 * Backend file-upload endpoints aren't wired yet; this stub keeps the route
 * navigable so the sidebar links don't 404. Replace with the real uploader
 * once `/api/v1/files` lands.
 */

import Link from "next/link";
import { FileUp } from "lucide-react";
import { AppShell } from "@/components/layout";
import { Button, Card, EmptyState } from "@/components/ui";

export default function FilesPage() {
  return (
    <AppShell
      eyebrow="DATA"
      title="Files"
      description="Upload CSV and Excel files for migration, validation, and reconciliation."
      crumbs={[{ label: "Files" }]}
    >
      <Card>
        <EmptyState
          icon={<FileUp className="h-5 w-5" />}
          title="File library is coming soon"
          description="Drag-and-drop uploads, schema inference, and per-file lineage will land once the file-storage service ships."
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
