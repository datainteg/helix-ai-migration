"use client";

/**
 * /projects/[id]/compliance — Compliance bundle export.
 *
 * One-shot screen: explains what's in the bundle, lets an admin download the
 * PDF, and shows when the last export ran (read from /audit-logs by entity
 * type "project" + action "compliance_bundle_exported").
 */

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Download, ShieldCheck, FileText } from "lucide-react";

import { ProjectShell } from "@/components/layout/ProjectShell";
import { Button, Card, ErrorBanner } from "@/components/ui";
import { useAuth } from "@/lib/auth-context";
import { useRegisterCrumbLabel } from "@/lib/breadcrumbs";
import { useProjectKey } from "@/lib/projects/useProjectKey";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export default function ProjectCompliancePage() {
  const projectKey = String(useParams<{ id: string }>().id);
  const { id } = useProjectKey(projectKey);
  const { token } = useAuth();
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState("");
  const [projectName, setProjectName] = useState("Project");
  const [projectStatus, setProjectStatus] = useState("draft");
  const [onHold, setOnHold] = useState(false);

  useRegisterCrumbLabel(projectKey, projectName !== "Project" ? projectName : undefined);

  // Real project name + status for the ProjectShell header + breadcrumb.
  useEffect(() => {
    if (!id) return;
    fetch(`${API_BASE}/api/v1/projects/${id}`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((p) => {
        setProjectName(p?.name || "Project");
        if (p?.status) setProjectStatus(p.status);
        setOnHold(!!p?.on_hold);
      })
      .catch(() => setProjectName("Project"));
  }, [id]);

  const download = async () => {
    if (!id) return;
    setDownloading(true);
    setError("");
    try {
      // SC-010: auth via the HttpOnly cookie (credentials:"include").
      const res = await fetch(`${API_BASE}/api/v1/projects/${id}/compliance-bundle`, {
        credentials: "include",
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(detail.detail || `Export failed (${res.status})`);
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `helix-compliance-${id}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Export failed");
    } finally {
      setDownloading(false);
    }
  };

  return (
    <ProjectShell
      projectId={projectKey}
      projectName={projectName}
      projectStatus={projectStatus as any}
      onHold={onHold}
      subtitle="SOC 2 / HIPAA-style evidence bundle for this project."
    >
      {error && <ErrorBanner message={error} onDismiss={() => setError("")} />}
      <div className="grid grid-cols-1 lg:grid-cols-[1.4fr_1fr] gap-4">
        <Card title={<span className="flex items-center gap-2"><ShieldCheck className="h-4 w-4 text-[var(--con-brand)]" /> Compliance bundle</span>}>
          <p className="text-[13px] text-ink-2 leading-relaxed">
            Generates a single PDF dump that auditors can take away as evidence
            for this project. Includes the project header, the per-project
            audit-chain entries (with HMAC head), every validation + recon
            run, cutover transitions, and the artifact registry (rollback
            links flagged).
          </p>
          <ul className="mt-4 space-y-1.5 text-[12.5px] text-ink-3">
            <li className="flex gap-2"><FileText className="h-3.5 w-3.5 mt-0.5 text-ink-4" /> Audit chain · cryptographic head per entry</li>
            <li className="flex gap-2"><FileText className="h-3.5 w-3.5 mt-0.5 text-ink-4" /> Validation runs · passed / failed counts</li>
            <li className="flex gap-2"><FileText className="h-3.5 w-3.5 mt-0.5 text-ink-4" /> Recon runs · diff summaries</li>
            <li className="flex gap-2"><FileText className="h-3.5 w-3.5 mt-0.5 text-ink-4" /> Cutovers · state-transition timestamps</li>
            <li className="flex gap-2"><FileText className="h-3.5 w-3.5 mt-0.5 text-ink-4" /> Artifacts · rollback-link flags</li>
          </ul>
          <div className="mt-5">
            <Button onClick={() => void download()} disabled={downloading}>
              <Download className="h-3.5 w-3.5" />
              {downloading ? "Generating…" : "Download PDF bundle"}
            </Button>
          </div>
        </Card>
        <Card title="When to export">
          <p className="text-[12.5px] text-ink-3 leading-relaxed">
            Operators typically export a fresh bundle before every release
            cut. The audit-chain HMAC head means a downloaded PDF is verifiable
            against the live chain at /audit-logs/verify.
          </p>
          <p className="text-[12.5px] text-ink-3 leading-relaxed mt-3">
            The export records an audit entry of its own
            (<code className="font-mono text-[11.5px]">compliance_bundle_exported</code>),
            so subsequent regulator queries about "who took evidence away" are
            answered from the same chain.
          </p>
        </Card>
      </div>
    </ProjectShell>
  );
}
