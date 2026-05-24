"use client";

import { useAuth } from "@/lib/auth-context";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Play, ShieldAlert, AlertTriangle, CheckCircle2, FileCode, History } from "lucide-react";
import { AppShell } from "@/components/layout";
import { Card, Button, Chip, ErrorBanner, LoadingState } from "@/components/ui";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface SecurityFinding {
  severity: string;
  description: string;
  location?: string;
}

interface ReviewResult {
  summary: string;
  quality_findings: string[];
  anti_patterns: string[];
  formatting_issues: string[];
  security_findings: SecurityFinding[];
  performance_issues: string[];
  maintainability_risks: string[];
  hardcoded_secrets_detected: boolean;
  assumptions: string[];
  limitations: string[];
  confidence_score?: number;
}

interface Artifact {
  id: string;
  filename: string;
  file_type: string;
  content_hash: string;
  storage_path: string;
}

export default function CodeReviewPage() {
  const { id } = useParams<{ id: string }>();
  const { token } = useAuth();
  const [artifact, setArtifact] = useState<Artifact | null>(null);
  const [review, setReview] = useState<ReviewResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!token || !id) return;
    fetch(`${API}/api/v1/artifacts/${id}`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => (r.ok ? r.json() : null))
      .then(setArtifact);
  }, [id, token]);

  const runReview = async () => {
    if (!id || !token) return;
    setError("");
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/v1/artifacts/${id}/review`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Review failed");
      }
      setReview(await res.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Review failed");
    } finally {
      setLoading(false);
    }
  };

  const severityChip = (s: string) =>
    s === "high" ? "red" : s === "medium" ? "amber" : "indigo";

  return (
    <AppShell
      title={artifact?.filename || "Code Review"}
      subtitle="AI code review with risks, suggestions, and approval actions."
      crumbs={[{ label: "Developer Workspace", href: "/developer-workspace" }, { label: artifact?.filename || "Artifact" }]}
      actions={<Button onClick={runReview} loading={loading}><Play className="h-4 w-4" />{review ? "Re-run Review" : "Run AI Review"}</Button>}
    >
      {error && <ErrorBanner message={error} onDismiss={() => setError("")} />}

      <div className="grid grid-cols-12 gap-4">
        {/* Left: artifact explorer */}
        <Card className="col-span-12 lg:col-span-3" title="Artifacts" padding="sm">
          <ul className="space-y-1 text-[12.5px]">
            <li className="px-2 py-1.5 rounded-md bg-helix-50 text-helix-700 flex items-center gap-2 truncate"><FileCode className="h-3.5 w-3.5" />{artifact?.filename || "current"}</li>
            <li className="px-2 py-1.5 rounded-md text-ink-3 flex items-center gap-2 truncate"><FileCode className="h-3.5 w-3.5" />plan_v1.md</li>
            <li className="px-2 py-1.5 rounded-md text-ink-3 flex items-center gap-2 truncate"><FileCode className="h-3.5 w-3.5" />ddl.sql</li>
            <li className="px-2 py-1.5 rounded-md text-ink-3 flex items-center gap-2 truncate"><FileCode className="h-3.5 w-3.5" />validate.sql</li>
          </ul>
          <hr className="border-hx my-3" />
          <p className="text-[11.5px] text-ink-3 uppercase tracking-wider font-medium mb-2 flex items-center gap-1"><History className="h-3 w-3" /> Versions</p>
          <ul className="space-y-1.5 text-[12px] text-ink-2">
            <li className="flex items-center justify-between"><span className="font-mono">v3 · current</span><Chip tone="indigo">latest</Chip></li>
            <li className="flex items-center justify-between"><span className="font-mono">v2</span><span className="text-ink-4 text-[11px]">2d ago</span></li>
            <li className="flex items-center justify-between"><span className="font-mono">v1</span><span className="text-ink-4 text-[11px]">5d ago</span></li>
          </ul>
        </Card>

        {/* Center: code / review */}
        <div className="col-span-12 lg:col-span-6 space-y-4">
          <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-2.5 text-[12.5px] text-red-700 flex items-start gap-2">
            <ShieldAlert className="h-4 w-4 mt-0.5 flex-shrink-0" />
            <span>Read uploaded files as text only. Code is never executed. Reviews are draft and require human approval.</span>
          </div>

          {artifact && (
            <Card title="Artifact" description={`.${artifact.file_type} · SHA256 ${artifact.content_hash?.slice(0, 16)}…`}>
              <p className="text-[12.5px] text-ink-3">Run AI Review to surface quality, security, and performance findings for this file.</p>
            </Card>
          )}

          {loading && <LoadingState label="Running AI review…" />}

          {review && (
            <>
              <Card title="AI Review Summary" actions={
                <>
                  {review.confidence_score != null && (
                    <Chip tone={review.confidence_score >= 0.8 ? "green" : review.confidence_score >= 0.5 ? "amber" : "red"}>
                      Confidence {(review.confidence_score * 100).toFixed(0)}%
                    </Chip>
                  )}
                  {review.hardcoded_secrets_detected && <Chip tone="red" dot>Secrets detected</Chip>}
                </>
              }>
                <p className="text-[13px] text-ink-2">{review.summary}</p>
              </Card>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Card title="Quality Findings">
                  <ul className="space-y-1 text-[12.5px] text-ink-2">
                    {review.quality_findings?.length ? review.quality_findings.map((f, i) => <li key={i}>• {f}</li>) : <li className="text-ink-4">None</li>}
                  </ul>
                  {review.anti_patterns?.length > 0 && (
                    <>
                      <p className="text-[11.5px] mt-3 mb-1 text-ink-3 uppercase tracking-wider font-medium">Anti-patterns</p>
                      <ul className="space-y-1 text-[12.5px] text-ink-2">{review.anti_patterns.map((f, i) => <li key={i}>• {f}</li>)}</ul>
                    </>
                  )}
                </Card>

                <Card title="Performance & Maintainability">
                  <ul className="space-y-1 text-[12.5px] text-ink-2">
                    {[...(review.performance_issues || []), ...(review.maintainability_risks || [])].length
                      ? [...(review.performance_issues || []), ...(review.maintainability_risks || [])].map((f, i) => <li key={i}>• {f}</li>)
                      : <li className="text-ink-4">None detected</li>}
                  </ul>
                </Card>
              </div>

              <Card title="Security Findings">
                {review.security_findings?.length ? (
                  <ul className="space-y-2">
                    {review.security_findings.map((f, i) => (
                      <li key={i} className="rounded-lg border border-hx px-3 py-2 text-[12.5px]">
                        <div className="flex items-center gap-2"><Chip tone={severityChip(f.severity) as "red" | "amber" | "indigo"}>{f.severity}</Chip><span className="text-ink-2">{f.description}</span></div>
                        {f.location && <p className="mt-1 text-[11px] text-ink-4 font-mono">Location: {f.location}</p>}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-[12.5px] text-ink-4">No security findings</p>
                )}
              </Card>

              <Card title="Assumptions & Limitations">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-[12.5px]">
                  <div>
                    <p className="text-ink-3 font-medium mb-1">Assumptions</p>
                    <ul className="space-y-1 text-ink-2">{review.assumptions?.map((a, i) => <li key={i}>• {a}</li>)}</ul>
                  </div>
                  <div>
                    <p className="text-ink-3 font-medium mb-1">Limitations</p>
                    <ul className="space-y-1 text-ink-2">{review.limitations?.map((l, i) => <li key={i}>• {l}</li>)}</ul>
                  </div>
                </div>
              </Card>
            </>
          )}

          {!review && !loading && artifact && (
            <Card><div className="py-10 text-center text-ink-3 text-[13px]">Click <strong className="text-ink">Run AI Review</strong> to analyze this artifact.</div></Card>
          )}
        </div>

        {/* Right: actions */}
        <Card className="col-span-12 lg:col-span-3" title="Review Actions">
          <div className="space-y-2">
            <Button className="w-full justify-center"><CheckCircle2 className="h-4 w-4" /> Approve</Button>
            <Button variant="outline" className="w-full justify-center"><AlertTriangle className="h-4 w-4 text-amber-500" /> Request Changes</Button>
            <Button variant="danger" className="w-full justify-center">Reject</Button>
            <Button variant="ghost" className="w-full justify-center">Regenerate</Button>
          </div>
          <hr className="border-hx my-4" />
          <p className="text-[11.5px] text-ink-3 uppercase tracking-wider font-medium mb-2">Reviewers</p>
          <ul className="space-y-1.5 text-[12.5px] text-ink-2">
            <li>Avery Johnson · Owner</li>
            <li>Sofia Marin · QA</li>
            <li>Rohan Patel · Architect</li>
          </ul>
        </Card>
      </div>
    </AppShell>
  );
}
