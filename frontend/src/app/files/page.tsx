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
            <Link href="/dashboard">
              <Button variant="outline">Back to Dashboard</Button>
            </Link>
          }
        />
      </Card>
    </AppShell>
  );
}
