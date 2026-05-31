"use client";

/**
 * /projects/[id]/migration — DEPRECATED.
 *
 * The migration run UI has been folded into the single canonical Workflows tab
 * (/agents). This route now redirects there so old links / bookmarks keep
 * working without showing a second, competing run UI.
 */

import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { LoadingState } from "@/components/ui";

export default function MigrationRedirectPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  useEffect(() => {
    if (id) router.replace(`/projects/${id}/agents`);
  }, [id, router]);
  return <LoadingState label="Redirecting to Workflows…" />;
}
