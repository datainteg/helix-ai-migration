"use client";

import React from "react";
import { Check, X, Info } from "lucide-react";

import { AppShell } from "@/components/layout";
import { Button, Card, DemoBanner } from "@/components/ui";

// TODO: hydrate from API
const APPROVAL_CONTEXT = {
  project: "Oracle GL -> Snowflake",
  projectId: "P-1042",
  workflow: "bmad-a8f3c2",
  reviewer: "Avery Johnson",
  ready: "16/16 checks passed",
  artifacts: [
    "context.md",
    "brief.md",
    "prd_v1.md",
    "ux_spec.md",
    "arch.md",
    "epics.md",
    "readiness.md",
  ],
};

// ─── Mock page chrome behind each variant ──────────────────
function MockPage({ blurred }: { blurred?: boolean }) {
  return (
    <div
      className="relative overflow-hidden bg-app pointer-events-none"
      style={{
        height: 360,
        filter: blurred ? "blur(2px) saturate(0.8)" : "none",
        opacity: blurred ? 0.55 : 1,
      }}
    >
      {/* Mock topbar */}
      <div
        className="flex items-center gap-2 border-b border-hx text-ink-4"
        style={{ height: 32, padding: "0 18px", fontSize: 10.5 }}
      >
        <span>Helix</span>
        <span>›</span>
        <span className="text-ink-2">Projects</span>
        <span>›</span>
        <span className="text-ink font-medium">Oracle GL -&gt; Snowflake</span>
      </div>
      {/* Mock page header */}
      <div style={{ padding: "16px 24px 12px" }}>
        <div className="eyebrow" style={{ fontSize: 9 }}>
          P-1042 · STARTED MAY 21
        </div>
        <div
          style={{
            fontSize: 22,
            fontWeight: 500,
            letterSpacing: "-0.02em",
            marginTop: 4,
          }}
        >
          Oracle GL -&gt; Snowflake
        </div>
      </div>
      {/* Mock content cards */}
      <div
        className="grid"
        style={{
          padding: "0 24px",
          gridTemplateColumns: "1fr 1fr 1fr",
          gap: 10,
        }}
      >
        {[60, 80, 40].map((h, i) => (
          <div
            key={i}
            className="bg-surface border border-hx"
            style={{ borderRadius: 8, height: h, padding: 10 }}
          >
            <div className="eyebrow" style={{ fontSize: 8.5 }}>
              METRIC {i + 1}
            </div>
            <div className="font-mono" style={{ fontSize: 18, marginTop: 4 }}>
              {[42, 78, 23][i]}%
            </div>
          </div>
        ))}
      </div>
      <div style={{ padding: "12px 24px" }}>
        <div
          className="bg-surface border border-hx"
          style={{ borderRadius: 8, padding: 12 }}
        >
          <div
            className="flex justify-between"
            style={{ marginBottom: 8 }}
          >
            <span style={{ fontSize: 12, fontWeight: 500 }}>
              Migration by schema
            </span>
            <span
              className="font-mono text-ink-4"
              style={{ fontSize: 10 }}
            >
              4 schemas
            </span>
          </div>
          {[100, 14, 0, 0].map((v, i) => (
            <div
              key={i}
              className="grid items-center"
              style={{
                gridTemplateColumns: "100px 1fr 60px",
                gap: 8,
                padding: "4px 0",
                fontSize: 11,
              }}
            >
              <span className="font-mono">
                GL_{["LEDGER", "TRANS", "RECON", "AUDIT"][i]}
              </span>
              <div
                className="bg-app-2"
                style={{ height: 3, borderRadius: 2 }}
              >
                <div
                  className="bg-ink"
                  style={{
                    width: `${v}%`,
                    height: "100%",
                    borderRadius: 2,
                  }}
                />
              </div>
              <span
                className="font-mono tabular-nums text-ink-3"
                style={{ fontSize: 10.5 }}
              >
                {v}%
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Variant A — inline side panel (current pattern) ───────
function VariantInline() {
  return (
    <div className="relative overflow-hidden" style={{ height: 360 }}>
      <div
        className="grid h-full"
        style={{ gridTemplateColumns: "1fr 220px" }}
      >
        <div className="bg-app overflow-hidden" style={{ padding: 18 }}>
          <div className="eyebrow" style={{ fontSize: 9 }}>
            BMAD WORKFLOW · {APPROVAL_CONTEXT.workflow}
          </div>
          <div
            style={{
              fontSize: 16,
              fontWeight: 600,
              marginTop: 4,
            }}
          >
            Oracle GL -&gt; Snowflake
          </div>
          <div
            className="flex flex-col"
            style={{ marginTop: 14, gap: 6 }}
          >
            {[
              "Mary — Product Brief",
              "John — PRD",
              "Sally — UX Design",
              "Winston — Architecture",
              "Winston — Readiness Check",
              "▼ Human Approval",
              "Amelia — Implementation",
              "Amelia — QA Tests",
            ].map((label, i) => {
              const isGate = label.includes("▼");
              const isCompleted = i < 5;
              return (
                <div
                  key={i}
                  className="bg-surface flex items-center"
                  style={{
                    border: `1px solid ${isGate ? "var(--con-warn)" : "var(--con-line)"}`,
                    borderRadius: 6,
                    padding: "6px 9px",
                    fontSize: 11.5,
                    gap: 8,
                    opacity: i > 5 ? 0.5 : 1,
                  }}
                >
                  <span
                    style={{
                      width: 14,
                      height: 14,
                      borderRadius: "50%",
                      background: isCompleted
                        ? "var(--con-ink-1)"
                        : isGate
                          ? "var(--con-warn)"
                          : "var(--con-surface)",
                      border:
                        isCompleted || isGate
                          ? "none"
                          : "1px solid var(--con-line-2)",
                    }}
                  />
                  <span
                    style={{
                      color: isGate ? "var(--con-warn)" : "var(--con-ink-2)",
                      fontWeight: isGate ? 600 : 400,
                    }}
                  >
                    {label}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
        {/* Inline panel */}
        <div
          className="flex flex-col bg-warn-soft"
          style={{
            borderLeft: "1px solid var(--con-warn)",
            padding: 14,
            gap: 10,
          }}
        >
          <div
            className="eyebrow"
            style={{ color: "var(--con-warn)", fontSize: 9 }}
          >
            HUMAN APPROVAL
          </div>
          <div
            style={{
              fontSize: 13,
              fontWeight: 600,
              lineHeight: 1.35,
            }}
          >
            Planning chain finished. Ready to start implementation?
          </div>
          <div
            className="text-ink-3"
            style={{ fontSize: 11, lineHeight: 1.5 }}
          >
            Architecture readiness{" "}
            <span className="font-mono text-ok">
              {APPROVAL_CONTEXT.ready}
            </span>
            . 7 artifacts generated by 5 agents.
          </div>
          <div
            className="flex flex-col"
            style={{ gap: 5, marginTop: 4 }}
          >
            <Button variant="primary" size="sm">
              <Check size={11} /> Approve
            </Button>
            <Button variant="outline" size="sm">
              <X size={11} /> Reject
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Variant B — full-page modal interrupt ─────────────────
function VariantModal() {
  return (
    <div className="relative overflow-hidden" style={{ height: 360 }}>
      <MockPage blurred />
      <div
        className="absolute inset-0 grid place-items-center"
        style={{
          background: "rgba(10,10,10,0.30)",
          padding: 18,
        }}
      >
        <div
          className="bg-surface overflow-hidden border border-hx shadow-lg"
          style={{
            borderRadius: 12,
            width: "min(420px, 100%)",
          }}
        >
          <div
            className="border-b border-hx"
            style={{ padding: "14px 18px 10px" }}
          >
            <div className="flex items-center" style={{ gap: 8 }}>
              <span
                style={{
                  display: "inline-block",
                  width: 14,
                  height: 14,
                  background: "var(--con-warn)",
                  transform: "rotate(45deg)",
                }}
              />
              <div
                className="eyebrow"
                style={{ color: "var(--con-warn)" }}
              >
                APPROVAL REQUIRED
              </div>
            </div>
            <div
              style={{
                fontSize: 15,
                fontWeight: 600,
                marginTop: 8,
              }}
            >
              Planning chain ready for review
            </div>
            <div
              className="text-ink-3"
              style={{ fontSize: 11.5, marginTop: 4 }}
            >
              <span className="font-mono">P-1042</span> · Oracle GL -&gt;
              Snowflake
            </div>
          </div>
          <div style={{ padding: "12px 18px" }}>
            <div
              className="grid"
              style={{
                gridTemplateColumns: "1fr 1fr",
                gap: 8,
                fontSize: 11.5,
              }}
            >
              <div>
                <div className="eyebrow" style={{ fontSize: 9 }}>
                  READINESS
                </div>
                <div
                  className="font-mono text-ok"
                  style={{ marginTop: 2 }}
                >
                  {APPROVAL_CONTEXT.ready}
                </div>
              </div>
              <div>
                <div className="eyebrow" style={{ fontSize: 9 }}>
                  ARTIFACTS
                </div>
                <div className="font-mono" style={{ marginTop: 2 }}>
                  7 generated
                </div>
              </div>
            </div>
          </div>
          <div
            className="flex justify-between items-center bg-surface-hi border-t border-hx"
            style={{ padding: "10px 18px" }}
          >
            <button
              type="button"
              className="bg-transparent border-0 text-ink-3"
              style={{ fontSize: 11.5 }}
            >
              Snooze 1h
            </button>
            <div className="flex" style={{ gap: 6 }}>
              <Button variant="outline" size="sm">
                <X size={11} /> Reject
              </Button>
              <Button variant="primary" size="sm">
                <Check size={11} /> Approve
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Variant C — persistent banner ─────────────────────────
function VariantBanner() {
  return (
    <div className="relative overflow-hidden" style={{ height: 360 }}>
      <div
        className="flex items-center bg-warn-soft"
        style={{
          borderBottom: "1px solid var(--con-warn)",
          padding: "10px 18px",
          gap: 12,
        }}
      >
        <span
          style={{
            display: "inline-block",
            width: 12,
            height: 12,
            background: "var(--con-warn)",
            transform: "rotate(45deg)",
            flexShrink: 0,
          }}
        />
        <div className="flex-1">
          <div
            className="text-warn"
            style={{ fontSize: 12.5, fontWeight: 500 }}
          >
            Approval needed: planning chain ready for review on Oracle GL -&gt;
            Snowflake
          </div>
          <div
            className="font-mono text-ink-3"
            style={{ fontSize: 10.5, marginTop: 2 }}
          >
            P-1042 · {APPROVAL_CONTEXT.workflow} · waiting 18s
          </div>
        </div>
        <div className="flex" style={{ gap: 6 }}>
          <Button variant="ghost" size="sm">
            Details ↗
          </Button>
          <Button variant="outline" size="sm">
            <X size={11} /> Reject
          </Button>
          <Button variant="primary" size="sm">
            <Check size={11} /> Approve
          </Button>
        </div>
      </div>
      <MockPage />
    </div>
  );
}

interface VariantCardProps {
  variant: string;
  title: string;
  eyebrow: string;
  pros: string[];
  cons: string[];
  recommendation?: string;
  children: React.ReactNode;
}

function VariantCard({
  variant,
  title,
  eyebrow,
  pros,
  cons,
  recommendation,
  children,
}: VariantCardProps) {
  return (
    <Card padding="md" bodyClassName="p-0">
      <div
        className="border-b border-hx"
        style={{ padding: "16px 18px 14px" }}
      >
        <div className="flex items-center" style={{ gap: 10 }}>
          <span
            className="bg-ink text-white font-mono font-semibold"
            style={{
              fontSize: 11,
              padding: "2px 8px",
              borderRadius: 4,
            }}
          >
            {variant}
          </span>
          <div className="eyebrow">{eyebrow}</div>
        </div>
        <div
          style={{
            fontSize: 17,
            fontWeight: 600,
            marginTop: 8,
            letterSpacing: "-0.005em",
          }}
        >
          {title}
        </div>
      </div>
      {/* Visual */}
      <div className="border-b border-hx">{children}</div>
      {/* Analysis */}
      <div
        className="grid"
        style={{
          padding: 18,
          gridTemplateColumns: "1fr 1fr",
          gap: 18,
        }}
      >
        <div>
          <div
            className="eyebrow"
            style={{ color: "var(--con-ok)" }}
          >
            STRENGTHS
          </div>
          <ul
            className="text-ink-2"
            style={{
              margin: "8px 0 0",
              paddingLeft: 14,
              fontSize: 12,
              lineHeight: 1.55,
            }}
          >
            {pros.map((p, i) => (
              <li key={i} style={{ marginBottom: 4 }}>
                {p}
              </li>
            ))}
          </ul>
        </div>
        <div>
          <div
            className="eyebrow"
            style={{ color: "var(--con-err)" }}
          >
            TRADE-OFFS
          </div>
          <ul
            className="text-ink-2"
            style={{
              margin: "8px 0 0",
              paddingLeft: 14,
              fontSize: 12,
              lineHeight: 1.55,
            }}
          >
            {cons.map((c, i) => (
              <li key={i} style={{ marginBottom: 4 }}>
                {c}
              </li>
            ))}
          </ul>
        </div>
      </div>
      {recommendation && (
        <div
          className="flex items-start bg-surface-hi border-t border-hx text-ink-3"
          style={{
            padding: "10px 18px",
            fontSize: 11.5,
            gap: 8,
          }}
        >
          <Info
            size={13}
            className="text-ink-4"
            style={{ marginTop: 1, flexShrink: 0 }}
          />
          <span>{recommendation}</span>
        </div>
      )}
    </Card>
  );
}

export default function ApprovalPage() {
  return (
    <AppShell
      eyebrow="DESIGN EXPLORATION · APPROVAL GATE UX"
      title="How should approval interrupt the operator?"
      description="Three patterns for the human-approval node in the BMAD pipeline. The right answer depends on how disruptive an approval ought to be — and how often it'll trigger across your team."
    >
      <div className="flex flex-col gap-4">
        {/* UI-035 — make explicit that everything below is a non-functional
            design mockup, not a live approval awaiting the operator. */}
        <DemoBanner message="Design exploration only. The variants below are static mockups of approval-gate UX — no real approval is pending and the buttons do nothing." />
        <VariantCard
          variant="A"
          eyebrow="INLINE SIDE PANEL · CURRENT PATTERN"
          title="Approval lives on the workflow detail page"
          pros={[
            "Zero interruption to operators not on this workflow",
            "All context already on the screen (artifacts, readiness, agent history)",
            "Comfortable for batch reviewers who plan to spend time here",
          ]}
          cons={[
            "Easy to miss — reviewer must navigate to the workflow",
            "Slow time-to-approval when reviewers aren't watching",
            "No global awareness across all pending approvals",
          ]}
          recommendation="Use as the default review surface. Pair with one of the patterns below for notification."
        >
          <VariantInline />
        </VariantCard>

        <VariantCard
          variant="B"
          eyebrow="FULL-PAGE MODAL INTERRUPT"
          title="Approval blocks the operator until acted on"
          pros={[
            "Impossible to miss — reviewer must approve, reject, or snooze",
            "Forces fast time-to-approval (minutes, not hours)",
            "Cleanly bounded decision context",
          ]}
          cons={[
            "Hostile if approvals fire often or to many people",
            "Tears reviewer out of whatever they were doing",
            "Limited canvas to surface evidence (artifacts, diff, history)",
          ]}
          recommendation="Reserve for high-severity gates — production cutovers, schema-destructive changes. Don't use for routine planning-chain approval."
        >
          <VariantModal />
        </VariantCard>

        <VariantCard
          variant="C"
          eyebrow="PERSISTENT TOP BANNER · OUR RECOMMENDATION"
          title="Awareness everywhere, action one click away"
          pros={[
            "Visible on every page until acted on — globally aware",
            "Non-blocking: operator can finish their thought before approving",
            "Quick-actions inline, full review one click away",
            "Stacks cleanly when multiple gates open (collapse to count)",
          ]}
          cons={[
            "Steals 40px of vertical space when present",
            "Tempting to approve without reading artifacts (mitigate: surface readiness summary)",
            "Needs design rules for stacking >1 pending approval",
          ]}
          recommendation="Best default: a top banner on every page when any approval is pending for the current user, with inline approve / reject / open buttons. Pair with email/Slack notifications via existing webhook."
        >
          <VariantBanner />
        </VariantCard>

        <Card title="Recommendation" eyebrow="DESIGN DIRECTION" padding="md">
          <p
            className="text-ink-2"
            style={{
              margin: 0,
              fontSize: 13,
              lineHeight: 1.65,
            }}
          >
            Combine <strong>A (inline panel)</strong> +{" "}
            <strong>C (persistent banner)</strong>. The banner provides global
            awareness and quick-action; the inline panel on the workflow page
            provides full context for considered review. Use{" "}
            <strong>B (modal)</strong> only for high-severity gates flagged at
            the workflow level — production cutovers, schema-destructive
            changes, anything that would trigger a follow-up incident if
            approved by accident.
          </p>
          <div
            className="grid"
            style={{
              marginTop: 12,
              gridTemplateColumns: "repeat(3, 1fr)",
              gap: 10,
              fontSize: 11.5,
            }}
          >
            {[
              {
                tier: "ROUTINE",
                desc: "Planning-chain approval, doc review",
                pattern: "Banner (C) + Panel (A)",
              },
              {
                tier: "ELEVATED",
                desc: "Schema migration, new connector",
                pattern: "Banner (C) + Panel (A) · 2 reviewers",
              },
              {
                tier: "CRITICAL",
                desc: "Prod cutover, destructive DDL",
                pattern: "Modal (B) · 2 reviewers · audit signature",
              },
            ].map((t) => (
              <div
                key={t.tier}
                className="border border-hx"
                style={{ borderRadius: 8, padding: "10px 12px" }}
              >
                <div className="eyebrow">{t.tier}</div>
                <div
                  className="text-ink-2"
                  style={{ marginTop: 5 }}
                >
                  {t.desc}
                </div>
                <div
                  className="font-mono text-ink"
                  style={{ marginTop: 5, fontSize: 11 }}
                >
                  -&gt; {t.pattern}
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </AppShell>
  );
}
