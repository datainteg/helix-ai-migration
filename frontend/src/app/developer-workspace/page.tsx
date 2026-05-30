"use client";

/**
 * /developer-workspace — Artifact review IDE.
 *
 * The three-pane IDE (artifact tree, version diff, AI review) is scoped to a
 * single project's artifacts. There is no project selected at this route yet,
 * so the page renders an honest empty state that points users to /projects to
 * open a workspace. No placeholder/sample artifacts, diffs, or reviews are shown.
 */

import Link from "next/link";
import { Folder } from "lucide-react";

import { AppShell } from "@/components/layout";
import { Button, EmptyState } from "@/components/ui";

export default function WorkspacePage() {
  return (
    <AppShell fullBleed>
      {/* Page header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-hx px-8 pt-5 pb-3.5">
        <div>
          <div className="eyebrow">DEVELOPER WORKSPACE</div>
          <h1 className="mt-1 mb-0 text-[22px] font-medium tracking-[-0.02em]">
            Review &amp; approve
          </h1>
        </div>
      </div>

      <div className="grid place-items-center" style={{ minHeight: "calc(100vh - 44px - 81px)" }}>
        <EmptyState
          icon={<Folder size={18} />}
          title="No workspace open"
          description="The review IDE opens against a project's generated artifacts. Open a project to browse its artifact tree, inspect version diffs, and review changes."
          action={
            <Link href="/projects">
              <Button variant="primary" size="md">
                Go to projects
              </Button>
            </Link>
          }
        />
      </div>
    </AppShell>
  );
}
