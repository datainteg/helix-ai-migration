"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { ProjectShell } from "@/components/layout/ProjectShell";
import { Card, LoadingState, ErrorBanner } from "@/components/ui";
import { ArtifactDiff } from "@/components/ArtifactDiff";
import { useProjectKey } from "@/lib/projects/useProjectKey";
import { useRegisterCrumbLabel } from "@/lib/breadcrumbs";
import * as api from "@/lib/lifecycle/api";
import type { MigrationArtifactVersion, VersionCompare } from "@/lib/lifecycle/api";

export default function ArtifactComparePage() {
  const params = useParams<{ id: string; artifactId: string }>();
  const projectParam = String(params.id);
  const artifactId = String(params.artifactId);
  const { key, name } = useProjectKey(projectParam);
  useRegisterCrumbLabel(projectParam, name);
  const sp = useSearchParams();
  const router = useRouter();

  const [versions, setVersions] = useState<MigrationArtifactVersion[]>([]);
  const [cmp, setCmp] = useState<VersionCompare | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const from = Number(sp.get("from"));
  const to = Number(sp.get("to"));

  useEffect(() => { api.getArtifactVersions(artifactId).then(setVersions).catch(() => {}); }, [artifactId]);

  const load = useCallback(async () => {
    if (!from || !to) { setLoading(false); return; }
    setLoading(true); setErr(null);
    try { setCmp(await api.compareVersions(artifactId, from, to)); }
    catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
    finally { setLoading(false); }
  }, [artifactId, from, to]);
  useEffect(() => { load(); }, [load]);

  function setVer(which: "from" | "to", val: number) {
    const params = new URLSearchParams(sp.toString());
    params.set(which, String(val));
    router.replace(`/projects/${key}/artifacts/${artifactId}/compare?${params.toString()}`);
  }

  const sel = (which: "from" | "to", value: number) => (
    <select value={value || ""} onChange={(e) => setVer(which, Number(e.target.value))}
      className="rounded-md border border-hx bg-app px-2 py-1 text-[13px] text-ink-1 focus:border-helix-400 focus:outline-none">
      <option value="" disabled>—</option>
      {versions.map((v) => <option key={v.id} value={v.version_number}>v{v.version_number} ({v.created_by_type})</option>)}
    </select>
  );

  return (
    <ProjectShell projectId={key} projectName={name || "Project"}>
      <Link href={`/projects/${key}/artifacts/${artifactId}/review`} className="inline-flex items-center gap-1.5 text-[12.5px] text-ink-3 hover:text-ink-1">
        <ArrowLeft className="h-3.5 w-3.5" /> Back to review
      </Link>
      {err && <ErrorBanner message={err} onDismiss={() => setErr(null)} />}

      <Card title="Compare versions">
        <div className="mb-4 flex flex-wrap items-center gap-3 text-[13px] text-ink-2">
          <span>From</span>{sel("from", from)}
          <span>→ To</span>{sel("to", to)}
          {cmp && <span className="text-[12px] text-ink-3"><span className="text-[var(--con-ok)]">+{cmp.added_lines}</span> / <span className="text-[var(--con-err)]">−{cmp.removed_lines}</span></span>}
        </div>
        {loading ? <LoadingState label="Computing diff…" />
          : !from || !to ? <p className="text-[13px] text-ink-3">Pick two versions to compare.</p>
          : cmp ? <ArtifactDiff oldContent={cmp.from_content} newContent={cmp.to_content} oldLabel={`v${cmp.from_version}`} newLabel={`v${cmp.to_version}`} />
          : null}
      </Card>
    </ProjectShell>
  );
}
