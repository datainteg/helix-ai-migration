"use client";

/**
 * /projects/[id]/sprints/approval — Sprint Approval Center.
 *
 * Centralizes every pending/approved/rejected/expired approval for the
 * active sprint. Tab-filterable, with optimistic UI feedback on approve/reject.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { ShieldCheck, CheckCircle2 } from "lucide-react";

import { AppShell } from "@/components/layout";
import {
  Button,
  Card,
  Chip,
  EmptyState,
  LoadingState,
  MetricCell,
  Tabs,
} from "@/components/ui";
import { SprintApprovalCard } from "@/components/sprints";
import { useAuth } from "@/lib/auth-context";
import {
  decideApproval,
  fetchActiveSprint,
  fetchApprovals,
  seedSprints,
  type Sprint,
  type SprintApproval,
} from "@/lib/sprints";

type Filter = "all" | "pending" | "approved" | "rejected";
type ApprovalStatus = SprintApproval["status"];

export default function SprintApprovalPage() {
  const params = useParams<{ id: string }>();
  const projectId = String(params?.id ?? "");
  const { token } = useAuth();

  const [active, setActive] = useState<Sprint | null>(null);
  const [approvals, setApprovals] = useState<SprintApproval[]>([]);
  const [filter, setFilter] = useState<Filter>("pending");
  const [decisions, setDecisions] = useState<Record<string, "approved" | "rejected">>({});
  const [loading, setLoading] = useState(true);
  const [seeding, setSeeding] = useState(false);

  const load = useCallback(() => {
    if (!token || !projectId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    fetchActiveSprint(token, projectId)
      .then(setActive)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [token, projectId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!token || !active) {
      setApprovals([]);
      return;
    }
    fetchApprovals(token, active.id)
      .then(setApprovals)
      .catch(() => setApprovals([]));
  }, [token, active]);

  const resolve = (a: SprintApproval): ApprovalStatus => decisions[a.id] ?? a.status;

  const counts = useMemo(() => {
    const c = { pending: 0, approved: 0, rejected: 0, expired: 0 };
    approvals.forEach((a) => {
      const final = resolve(a);
      if (final === "pending")  c.pending++;
      else if (final === "approved") c.approved++;
      else if (final === "rejected") c.rejected++;
      else if (final === "expired")  c.expired++;
    });
    return c;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [approvals, decisions]);

  const visible = useMemo(() => {
    return approvals.filter((a) => {
      const final = resolve(a);
      if (filter === "all") return true;
      return final === filter;
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [approvals, decisions, filter]);

  const handleApprove = (id: string) => {
    setDecisions((d) => ({ ...d, [id]: "approved" }));
    if (token) decideApproval(token, id, "approved").catch(() => {});
  };
  const handleReject = (id: string) => {
    setDecisions((d) => ({ ...d, [id]: "rejected" }));
    if (token) decideApproval(token, id, "rejected").catch(() => {});
  };

  const handleSeed = () => {
    if (!token || !projectId) return;
    setSeeding(true);
    seedSprints(token, projectId)
      .then(() => {
        load();
      })
      .catch(() => {})
      .finally(() => setSeeding(false));
  };

  if (loading) {
    return (
      <AppShell
        eyebrow={`SPRINTS · ${projectId}`}
        title="Approval center"
        crumbs={["Projects", projectId, "Sprints", "Approvals"]}
      >
        <LoadingState />
      </AppShell>
    );
  }

  if (!active) {
    return (
      <AppShell
        eyebrow={`SPRINTS · ${projectId}`}
        title="Approval center"
        crumbs={["Projects", projectId, "Sprints", "Approvals"]}
      >
        <Card>
          <EmptyState
            title="No active sprint"
            description="Start a sprint or run the seed to populate demo data."
            action={
              <Button variant="primary" loading={seeding} onClick={handleSeed}>
                Run seed
              </Button>
            }
          />
        </Card>
      </AppShell>
    );
  }

  return (
    <AppShell
      eyebrow={`SPRINTS · ${projectId}`}
      title="Approval center"
      description={`${counts.pending} pending approvals across ${active.name}.`}
      crumbs={["Projects", projectId, "Sprints", "Approvals"]}
    >
      {/* Metric strip */}
      <div className="grid grid-cols-4 bg-surface border border-hx rounded-[10px] divide-x divide-hx mb-6">
        <MetricCell big label="Pending"  value={counts.pending}  hint="Awaiting decision" accent={counts.pending > 0 ? "var(--con-warn)" : undefined} />
        <MetricCell big label="Approved" value={counts.approved} hint="This sprint" accent="var(--con-ok)" />
        <MetricCell big label="Rejected" value={counts.rejected} hint="This sprint" accent={counts.rejected > 0 ? "var(--con-err)" : undefined} />
        <MetricCell big label="Expired"  value={counts.expired}  hint="Past deadline" />
      </div>

      <div className="grid grid-cols-[1fr_280px] gap-4">
        <div>
          {/* Filter tabs */}
          <div className="mb-4">
            <Tabs
              value={filter}
              onChange={(v) => setFilter(v as Filter)}
              variant="pill"
              tabs={[
                { id: "all",      label: "All",      count: approvals.length },
                { id: "pending",  label: "Pending",  count: counts.pending },
                { id: "approved", label: "Approved", count: counts.approved },
                { id: "rejected", label: "Rejected", count: counts.rejected },
              ]}
            />
          </div>

          {visible.length === 0 ? (
            <Card>
              <EmptyState
                icon={<ShieldCheck className="h-4 w-4" />}
                title="Nothing in this view"
                description="Approvals appear here as gates open in the migration workflow."
              />
            </Card>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
              {visible.map((a) => {
                const final = resolve(a);
                const effective: SprintApproval = { ...a, status: final };
                return (
                  <div key={a.id}>
                    <SprintApprovalCard
                      approval={effective}
                      onApprove={() => handleApprove(a.id)}
                      onReject={() => handleReject(a.id)}
                    />
                    {decisions[a.id] && (
                      <div className="mt-2">
                        <Chip
                          tone={decisions[a.id] === "approved" ? "ok" : "err"}
                          dot
                        >
                          <CheckCircle2 className="h-3 w-3" />
                          {decisions[a.id] === "approved" ? "Approved by you" : "Rejected by you"}
                        </Chip>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Side: guidance */}
        <Card title="Approval guidance" eyebrow="POLICY">
          <div className="space-y-3 text-[12px] text-ink-2 leading-relaxed">
            <p>
              Approvals route to platform admins. Code reviews require the artifact
              owner <span className="font-medium text-ink">plus one approver</span>.
            </p>
            <p>
              Release gates require both <span className="font-mono text-ink">Validation ≥ 95%</span> and{" "}
              <span className="font-mono text-ink">Recon ≥ 99%</span> before the
              production go/no-go can be cast.
            </p>
            <div className="border-t border-hx pt-3 mt-3 space-y-2">
              <KindRow color="var(--con-warn)" label="Milestone" desc="Sprint phase exit" />
              <KindRow color="var(--con-info)" label="Code review" desc="Owner + 1 approver" />
              <KindRow color="var(--con-err)"  label="Release" desc="Platform admins" />
              <KindRow color="var(--con-brand)" label="Validation override" desc="Quality lead only" />
            </div>
          </div>
        </Card>
      </div>
    </AppShell>
  );
}

function KindRow({ color, label, desc }: { color: string; label: string; desc: string }) {
  return (
    <div className="flex items-start gap-2">
      <span className="h-2 w-2 rounded-full mt-1.5 flex-shrink-0" style={{ background: color }} />
      <div className="text-[11.5px]">
        <span className="font-medium text-ink">{label}</span>
        <span className="text-ink-4"> — {desc}</span>
      </div>
    </div>
  );
}
