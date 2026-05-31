"use client";

import { MarkdownView, EmptyState } from "@/components/ui";

// Read-only markdown artifact viewer.
export function ArtifactViewer({ markdown }: { markdown: string | null | undefined }) {
  if (!markdown || !markdown.trim()) {
    return <EmptyState title="No content" description="This artifact version has no markdown content." />;
  }
  return <MarkdownView text={markdown} className="hx-md" />;
}
