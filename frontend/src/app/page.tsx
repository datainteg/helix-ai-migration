import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = { title: "Helix — AI-Powered Database Migration" };
import {
  ArrowRight,
  Github,
  Play,
  Bot,
  ShieldCheck,
  GitCompareArrows,
  TerminalSquare,
  Plug,
  Database,
  Sparkles,
  Workflow,
  CheckCircle2,
  Container,
  Boxes,
} from "lucide-react";
import { WebsiteNav } from "@/components/website/WebsiteNav";
import { WebsiteFooter } from "@/components/website/WebsiteFooter";
import { HeroHelixArt } from "@/components/layout/HelixLogo";
import { Chip } from "@/components/ui/Chip";

export default function LandingPage() {
  return (
    <div className="min-h-screen flex flex-col bg-app">
      <WebsiteNav />

      {/* Hero */}
      <section className="relative pt-24 pb-16 overflow-hidden">
        <div
          aria-hidden
          className="absolute inset-0 pointer-events-none"
          style={{
            background:
              "radial-gradient(ellipse 60% 40% at 50% 0%, rgba(139,92,246,0.12), transparent 70%), radial-gradient(ellipse 60% 40% at 50% 30%, rgba(6,182,212,0.08), transparent 70%)",
          }}
        />
        <div
          aria-hidden
          className="absolute inset-0 hx-grid-bg pointer-events-none"
          style={{
            maskImage: "radial-gradient(ellipse 70% 50% at 50% 30%, #000 30%, transparent 80%)",
            WebkitMaskImage: "radial-gradient(ellipse 70% 50% at 50% 30%, #000 30%, transparent 80%)",
          }}
        />
        <div className="relative max-w-[1200px] mx-auto px-8 text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-surface border border-hx shadow-xs text-[12.5px] text-ink-2">
            <span className="px-2 py-0.5 rounded-full bg-soft-indigo text-helix-700 font-semibold text-[10.5px] uppercase tracking-wide">
              v0.4.2
            </span>
            <span>Agent canvas + Databricks notebook generator now in beta</span>
            <ArrowRight className="h-3 w-3 text-ink-4" />
          </div>

          <h1 className="mt-6 text-[44px] sm:text-[64px] md:text-[72px] font-semibold tracking-tight leading-[1.02] text-ink">
            The migration command center
            <br />
            <span className="bg-clip-text text-transparent bg-indigo-cyan">built for AI agents.</span>
          </h1>

          <p className="mx-auto max-w-2xl mt-6 text-[17px] sm:text-[18px] leading-[1.55] text-ink-3">
            Open-source, self-hosted platform to plan, validate, reconcile, and ship complex enterprise data
            migrations — with multi-agent workflows that your architects and engineers can actually review.
          </p>

          <div className="mt-8 flex flex-wrap gap-3 justify-center">
            <Link
              href="/setup/first-admin"
              className="inline-flex items-center gap-2 h-12 px-6 rounded-xl bg-indigo-violet text-white text-[14px] font-medium shadow-glow hover:shadow-glow-lg hover:-translate-y-px transition-all"
            >
              Get Started <ArrowRight className="h-4 w-4" />
            </Link>
            <a
              href="https://github.com/datainteg/helix-ai-migration"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-2 h-12 px-6 rounded-xl bg-surface border border-hx text-ink text-[14px] font-medium hover:bg-zinc-50 transition-colors"
            >
              <Github className="h-4 w-4" /> View on GitHub
            </a>
            <a
              href="https://github.com/datainteg/helix-ai-migration#readme"
              className="inline-flex items-center gap-2 h-12 px-6 rounded-xl text-ink-2 text-[14px] hover:bg-zinc-100 transition-colors"
            >
              <Play className="h-4 w-4 fill-current" /> Read Docs
            </a>
          </div>

          <div className="mt-5 flex flex-wrap justify-center gap-6 text-[12.5px] text-ink-3">
            <span>✓ Apache 2.0</span>
            <span>✓ Self-hosted</span>
            <span>✓ Bring your own LLM</span>
            <span>✓ SOC 2-ready audit trail</span>
          </div>

          {/* Hero product mock */}
          <div className="mt-14 mx-auto max-w-[1100px] rounded-2xl border border-hx bg-surface shadow-hero overflow-hidden">
            <HeroProductMock />
          </div>
        </div>
      </section>

      {/* Trusted by / migration sources */}
      <section className="border-y border-hx-2 bg-app-2/40">
        <div className="max-w-[1200px] mx-auto px-8 py-10 text-center">
          <p className="text-[11.5px] uppercase tracking-wider text-ink-4 font-medium">Migrate from / to</p>
          <div className="mt-4 flex flex-wrap justify-center gap-x-10 gap-y-3 text-[14px] font-medium text-ink-3">
            {["Oracle", "SAS", "SQL Server", "Salesforce", "DataStage", "Snowflake", "Databricks", "PostgreSQL", "S3"].map((n) => (
              <span key={n}>{n}</span>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="py-24">
        <div className="max-w-[1200px] mx-auto px-8">
          <SectionHead
            eyebrow="The platform"
            title="One command center for every migration"
            description="From requirement intake to production cut-over, every step is an artifact you can review, approve, and roll back."
          />
          <div className="mt-12 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            <FeatureCard
              icon={<Bot className="h-5 w-5" />}
              title="Multi-agent workflow"
              text="BA · Architect · Data Engineer · QA · Recon · DevOps agents collaborate with typed outputs and human approval gates."
            />
            <FeatureCard
              icon={<ShieldCheck className="h-5 w-5" />}
              title="Validation center"
              text="Schema, row-count, null, duplicate, distribution, and business-rule checks with run history and trends."
            />
            <FeatureCard
              icon={<GitCompareArrows className="h-5 w-5" />}
              title="Reconciliation dashboard"
              text="Source ↔ target counts, mismatches, missing & extra records, with categorized anomalies and per-table scores."
            />
            <FeatureCard
              icon={<TerminalSquare className="h-5 w-5" />}
              title="Developer workspace"
              text="Three-pane IDE for review: artifact explorer, code/diff/notebook, AI review panel with risks and suggestions."
            />
            <FeatureCard
              icon={<Plug className="h-5 w-5" />}
              title="Connector framework"
              text="PostgreSQL, MySQL, SQL Server, Snowflake, S3, CSV, Excel, and pluggable custom connectors."
            />
            <FeatureCard
              icon={<Sparkles className="h-5 w-5" />}
              title="Bring your own LLM"
              text="OpenAI, Claude, Gemini, DeepSeek, OpenRouter, or any OpenAI-compatible local model. Per-agent routing."
            />
          </div>
        </div>
      </section>

      {/* Architecture */}
      <section id="architecture" className="py-24 bg-app-2/40 border-y border-hx-2">
        <div className="max-w-[1200px] mx-auto px-8">
          <SectionHead
            eyebrow="Architecture"
            title="Self-hosted, container-native"
            description="FastAPI + PostgreSQL + Redis + Temporal + LangGraph + PydanticAI. Run on your infrastructure with one compose file."
          />
          <div className="mt-12 grid grid-cols-1 lg:grid-cols-2 gap-8 items-start">
            <ArchitectureGraphic />
            <div className="space-y-4">
              {[
                ["FastAPI", "Typed API surface, OpenAPI auto-gen, JWT auth, RBAC."],
                ["Temporal", "Durable agent workflows with retries, replay, and human approvals."],
                ["LangGraph + PydanticAI", "Typed multi-agent orchestration with structured outputs."],
                ["PostgreSQL + Redis", "Source of truth + caching for runs, artifacts, and audit logs."],
              ].map(([t, d]) => (
                <div key={t} className="rounded-2xl border border-hx bg-surface p-5 shadow-xs">
                  <div className="text-[14px] font-semibold text-ink">{t}</div>
                  <div className="mt-1 text-[13px] text-ink-3">{d}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Agent workflow */}
      <section id="agents" className="py-24">
        <div className="max-w-[1200px] mx-auto px-8">
          <SectionHead
            eyebrow="Agent canvas"
            title="Workflows you can actually review"
            description="Every agent emits typed artifacts. Human approval gates between phases. Replayable with full audit trail."
          />
          <div className="mt-12 rounded-2xl border border-hx bg-surface p-6 sm:p-10 shadow-soft">
            <AgentFlowDiagram />
          </div>
        </div>
      </section>

      {/* Validation + Recon */}
      <section className="py-24 bg-app-2/40 border-y border-hx-2">
        <div className="max-w-[1200px] mx-auto px-8 grid grid-cols-1 lg:grid-cols-2 gap-8">
          <FeatureBlock
            eyebrow="Validation"
            title="Trust your data, then ship it"
            bullets={[
              "Schema equivalence + drift detection",
              "Row count, null, duplicate, distribution checks",
              "Business-rule validations from BA agent",
              "Pass / fail / warning donut summaries",
            ]}
            icon={<ShieldCheck className="h-5 w-5" />}
          />
          <FeatureBlock
            eyebrow="Reconciliation"
            title="Find every mismatch, before prod"
            bullets={[
              "Source vs target counts per table",
              "Matched / mismatched / missing / extra records",
              "Anomaly categories with drill-down",
              "Recon score trend over time",
            ]}
            icon={<GitCompareArrows className="h-5 w-5" />}
          />
        </div>
      </section>

      {/* Developer Workspace */}
      <section className="py-24">
        <div className="max-w-[1200px] mx-auto px-8 grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
          <div>
            <Chip tone="violet">Developer workspace</Chip>
            <h2 className="mt-3 text-[34px] sm:text-[42px] font-semibold tracking-tight text-ink leading-tight">
              Three panels. Every artifact reviewable.
            </h2>
            <p className="mt-4 text-[15px] text-ink-3 max-w-xl">
              Left: artifact explorer with versions. Center: code, notebook, diff. Right: AI review panel with risks
              and approval actions. Generated code is treated as draft until you sign off.
            </p>
            <ul className="mt-6 space-y-2 text-[14px] text-ink-2">
              {[
                "Side-by-side diff between original and migrated code",
                "Inline AI suggestions with security / performance risks",
                "Approve, reject, regenerate, or comment per version",
                "Artifact version history with full audit trail",
              ].map((line) => (
                <li key={line} className="flex items-start gap-2">
                  <CheckCircle2 className="h-4 w-4 text-emerald-500 mt-0.5 flex-shrink-0" />
                  <span>{line}</span>
                </li>
              ))}
            </ul>
          </div>
          <DevWorkspaceMock />
        </div>
      </section>

      {/* Connector framework */}
      <section className="py-24 bg-app-2/40 border-y border-hx-2">
        <div className="max-w-[1200px] mx-auto px-8 text-center">
          <SectionHead
            eyebrow="Connectors"
            title="Plug into anything"
            description="First-class connectors for databases, warehouses, files, and object storage — plus a custom connector SDK."
          />
          <div className="mt-10 grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3">
            {[
              "PostgreSQL",
              "MySQL",
              "SQL Server",
              "Snowflake",
              "S3",
              "CSV",
              "Excel",
              "Custom",
            ].map((n) => (
              <div
                key={n}
                className="rounded-xl border border-hx bg-surface p-4 text-center text-[13px] font-medium text-ink-2 hover:shadow-soft transition-shadow"
              >
                <Database className="h-5 w-5 mx-auto text-ink-4 mb-2" />
                {n}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* OSS / Docker install */}
      <section id="open-source" className="py-24">
        <div className="max-w-[1200px] mx-auto px-8 grid grid-cols-1 lg:grid-cols-2 gap-10 items-center">
          <div>
            <Chip tone="cyan" dot>
              Apache 2.0
            </Chip>
            <h2 className="mt-3 text-[34px] sm:text-[42px] font-semibold tracking-tight text-ink leading-tight">
              Run it on your infra
              <br />
              in <span className="bg-clip-text text-transparent bg-indigo-cyan">one command.</span>
            </h2>
            <p className="mt-4 text-[15px] text-ink-3 max-w-xl">
              No telemetry. No phone-home. Your data stays in your VPC. Bring your own LLM keys, or run a local model.
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <a
                href="https://github.com/datainteg/helix-ai-migration"
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-2 h-11 px-5 rounded-xl bg-ink text-white text-[14px] font-medium hover:bg-zinc-800 transition-colors"
              >
                <Github className="h-4 w-4" /> Star on GitHub
              </a>
              <a
                href="https://github.com/datainteg/helix-ai-migration#readme"
                className="inline-flex items-center gap-2 h-11 px-5 rounded-xl border border-hx bg-surface text-[14px] text-ink hover:bg-zinc-50 transition-colors"
              >
                Read Docs <ArrowRight className="h-4 w-4" />
              </a>
            </div>
          </div>
          <div className="rounded-2xl border border-hx bg-ink text-zinc-100 p-5 sm:p-6 shadow-hero font-mono text-[12.5px] leading-[1.7]">
            <div className="flex items-center gap-1.5 mb-4">
              <span className="h-2.5 w-2.5 rounded-full bg-red-500/80" />
              <span className="h-2.5 w-2.5 rounded-full bg-amber-500/80" />
              <span className="h-2.5 w-2.5 rounded-full bg-emerald-500/80" />
              <span className="ml-3 text-zinc-500 text-[11px]">~/projects · install.sh</span>
            </div>
            <div className="text-emerald-400">$ git clone https://github.com/datainteg/helix-ai-migration.git</div>
            <div className="text-emerald-400">$ cd helix-ai-migration</div>
            <div className="text-emerald-400">$ docker compose up -d</div>
            <div className="text-zinc-400 mt-3"># Open http://localhost:3000 → first-admin setup</div>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-24">
        <div className="max-w-[1100px] mx-auto px-8">
          <div className="rounded-3xl border border-hx bg-indigo-cyan p-12 text-center text-white shadow-hero">
            <h2 className="text-[34px] sm:text-[44px] font-semibold tracking-tight">
              Stop migrating with spreadsheets.
            </h2>
            <p className="mt-3 text-[16px] text-white/80 max-w-xl mx-auto">
              Helix Migration is open-source. Self-host today. Bring your own LLM. Ship migrations your auditors will thank you for.
            </p>
            <div className="mt-7 flex flex-wrap gap-3 justify-center">
              <Link
                href="/setup/first-admin"
                className="inline-flex items-center gap-2 h-12 px-7 rounded-xl bg-white text-ink text-[14px] font-medium hover:bg-zinc-100 transition-colors"
              >
                Get Started <ArrowRight className="h-4 w-4" />
              </Link>
              <a
                href="https://github.com/datainteg/helix-ai-migration"
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-2 h-12 px-7 rounded-xl bg-white/10 text-white text-[14px] font-medium hover:bg-white/20 border border-white/30 transition-colors"
              >
                <Github className="h-4 w-4" /> View on GitHub
              </a>
            </div>
          </div>
        </div>
      </section>

      <WebsiteFooter />
    </div>
  );
}

function SectionHead({ eyebrow, title, description }: { eyebrow: string; title: string; description: string }) {
  return (
    <div className="text-center max-w-3xl mx-auto">
      <div className="text-[12px] uppercase tracking-wider text-helix-600 font-semibold">{eyebrow}</div>
      <h2 className="mt-2 text-[30px] sm:text-[42px] font-semibold tracking-tight text-ink leading-tight">{title}</h2>
      <p className="mt-3 text-[15px] text-ink-3">{description}</p>
    </div>
  );
}

function FeatureCard({ icon, title, text }: { icon: React.ReactNode; title: string; text: string }) {
  return (
    <div className="rounded-2xl border border-hx bg-surface p-6 shadow-xs hover:shadow-soft transition-shadow">
      <div className="grid place-items-center h-10 w-10 rounded-xl bg-soft-indigo text-helix-600">{icon}</div>
      <h3 className="mt-4 text-[15px] font-semibold text-ink">{title}</h3>
      <p className="mt-1.5 text-[13px] text-ink-3 leading-relaxed">{text}</p>
    </div>
  );
}

function FeatureBlock({
  eyebrow,
  title,
  bullets,
  icon,
}: {
  eyebrow: string;
  title: string;
  bullets: string[];
  icon: React.ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-hx bg-surface p-8 shadow-soft">
      <div className="flex items-center gap-2 text-helix-600">
        <div className="grid place-items-center h-8 w-8 rounded-lg bg-soft-indigo">{icon}</div>
        <div className="text-[12px] uppercase tracking-wider font-semibold">{eyebrow}</div>
      </div>
      <h3 className="mt-4 text-[24px] font-semibold tracking-tight text-ink">{title}</h3>
      <ul className="mt-4 space-y-2 text-[14px] text-ink-2">
        {bullets.map((b) => (
          <li key={b} className="flex items-start gap-2">
            <CheckCircle2 className="h-4 w-4 text-emerald-500 mt-0.5 flex-shrink-0" />
            <span>{b}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function HeroProductMock() {
  return (
    <div className="grid grid-cols-12 min-h-[420px]">
      <div className="hidden md:flex col-span-2 border-r border-hx bg-app-2/40 p-4 flex-col gap-1.5 text-[12px]">
        {["Overview", "Projects", "Agents", "Validation", "Recon", "Connectors", "Reports", "Admin"].map((l, i) => (
          <div
            key={l}
            className={`px-2 py-1.5 rounded-md ${i === 0 ? "bg-helix-50 text-helix-700 font-medium" : "text-ink-3"}`}
          >
            {l}
          </div>
        ))}
      </div>
      <div className="col-span-12 md:col-span-10 p-6">
        <div className="text-[11px] uppercase tracking-wider text-ink-4 font-medium">Migration Command Center</div>
        <div className="text-[22px] font-semibold tracking-tight text-ink mt-1">24 projects · 96.5% recon score</div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-5">
          {[
            { l: "Active", v: "24", c: "#6366F1" },
            { l: "Validation", v: "92%", c: "#10B981" },
            { l: "Recon", v: "96.5%", c: "#06B6D4" },
            { l: "Approvals", v: "18", c: "#F59E0B" },
          ].map((m) => (
            <div key={m.l} className="rounded-xl border border-hx bg-surface p-3">
              <div className="text-[10.5px] uppercase tracking-wider text-ink-4">{m.l}</div>
              <div className="mt-1 text-[22px] font-semibold" style={{ color: m.c }}>
                {m.v}
              </div>
            </div>
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-3 mt-4">
          <div className="lg:col-span-2 rounded-xl border border-hx bg-surface p-4 h-[180px]">
            <div className="text-[12px] text-ink-3 mb-2">Migration progress trend</div>
            <svg viewBox="0 0 400 120" className="w-full h-[140px]">
              <defs>
                <linearGradient id="lp-area" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#6366F1" stopOpacity="0.25" />
                  <stop offset="100%" stopColor="#6366F1" stopOpacity="0" />
                </linearGradient>
              </defs>
              <path d="M0,90 C50,80 100,72 150,55 C200,40 250,38 300,25 C350,18 380,15 400,12 L400,120 L0,120 Z" fill="url(#lp-area)" />
              <path
                d="M0,90 C50,80 100,72 150,55 C200,40 250,38 300,25 C350,18 380,15 400,12"
                fill="none"
                stroke="#6366F1"
                strokeWidth="2"
              />
            </svg>
          </div>
          <div className="rounded-xl border border-hx bg-surface p-4 h-[180px] flex flex-col">
            <div className="text-[12px] text-ink-3 mb-2">Validation summary</div>
            <div className="flex-1 flex items-center justify-center">
              <div className="relative h-[120px] w-[120px]">
                <svg viewBox="0 0 100 100" className="absolute inset-0">
                  <circle cx="50" cy="50" r="40" stroke="#F1F5F9" strokeWidth="12" fill="none" />
                  <circle
                    cx="50"
                    cy="50"
                    r="40"
                    stroke="#10B981"
                    strokeWidth="12"
                    fill="none"
                    strokeDasharray="220 100"
                    transform="rotate(-90 50 50)"
                  />
                </svg>
                <div className="absolute inset-0 grid place-items-center text-[18px] font-semibold text-ink">2,341</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function ArchitectureGraphic() {
  const Node = ({ title, sub, accent }: { title: string; sub: string; accent: string }) => (
    <div className="rounded-xl border border-hx bg-surface p-3.5 shadow-xs">
      <div className="text-[12.5px] font-semibold text-ink">{title}</div>
      <div className="text-[11.5px] text-ink-3 mt-0.5">{sub}</div>
      <div className="mt-2 h-1 rounded-full" style={{ background: accent }} />
    </div>
  );
  return (
    <div className="rounded-2xl border border-hx bg-surface p-6 shadow-soft">
      <div className="grid grid-cols-2 gap-3">
        <Node title="Next.js Frontend" sub="App router · TS · Tailwind" accent="#6366F1" />
        <Node title="FastAPI" sub="REST + OpenAPI · JWT" accent="#8B5CF6" />
        <Node title="Temporal" sub="Durable workflows" accent="#06B6D4" />
        <Node title="LangGraph + PydanticAI" sub="Typed multi-agent" accent="#10B981" />
        <Node title="PostgreSQL" sub="Source of truth" accent="#F59E0B" />
        <Node title="Redis" sub="Queue & cache" accent="#DC2626" />
      </div>
      <div className="mt-5 flex items-center gap-2 text-[11.5px] text-ink-3">
        <Container className="h-3.5 w-3.5" /> docker compose up -d
        <span className="mx-1">·</span>
        <Boxes className="h-3.5 w-3.5" /> 5 containers
        <span className="mx-1">·</span>
        <Workflow className="h-3.5 w-3.5" /> 1 minute install
      </div>
    </div>
  );
}

function AgentFlowDiagram() {
  const agents = [
    { name: "Requirement Intake", color: "#E0E7FF", ink: "#4338CA" },
    { name: "BA Agent", color: "#EEF2FF", ink: "#4F46E5" },
    { name: "Architect Agent", color: "#F5F3FF", ink: "#7C3AED" },
    { name: "Human Approval", color: "#FEF3C7", ink: "#92400E" },
    { name: "Data Engineer", color: "#ECFEFF", ink: "#0E7490" },
    { name: "QA Agent", color: "#DCFCE7", ink: "#15803D" },
    { name: "Recon Agent", color: "#E0E7FF", ink: "#4338CA" },
    { name: "DevOps Agent", color: "#FCE7F3", ink: "#9D174D" },
    { name: "PM / Final Review", color: "#F1F5F9", ink: "#0F172A" },
  ];
  return (
    <div className="flex flex-wrap items-center justify-center gap-3">
      {agents.map((a, i) => (
        <div key={a.name} className="flex items-center gap-3">
          <div
            className="rounded-xl px-4 py-3 text-[13px] font-medium shadow-xs border border-hx"
            style={{ background: a.color, color: a.ink }}
          >
            {a.name}
          </div>
          {i < agents.length - 1 && <ArrowRight className="h-3.5 w-3.5 text-ink-4" />}
        </div>
      ))}
    </div>
  );
}

function DevWorkspaceMock() {
  return (
    <div className="rounded-2xl border border-hx bg-surface shadow-soft overflow-hidden">
      <div className="grid grid-cols-12 min-h-[340px] text-[12px]">
        <div className="col-span-3 border-r border-hx bg-app-2/40 p-3 space-y-1">
          <div className="text-ink-4 text-[10.5px] uppercase tracking-wider mb-1.5">Artifacts</div>
          {["plan_v1.md", "ddl.sql", "migrate.py", "validate.sql", "notebook.ipynb"].map((f, i) => (
            <div
              key={f}
              className={`px-2 py-1 rounded ${i === 2 ? "bg-helix-50 text-helix-700" : "text-ink-3"}`}
            >
              {f}
            </div>
          ))}
        </div>
        <div className="col-span-6 border-r border-hx p-3 font-mono text-[11.5px] text-ink-2 bg-app">
          <div className="text-ink-4 mb-2 text-[10.5px] uppercase tracking-wider font-sans">migrate.py · diff</div>
          <div className="text-emerald-700 bg-emerald-50 -mx-3 px-3">+ from helix.runtime import session</div>
          <div className="text-emerald-700 bg-emerald-50 -mx-3 px-3">+ df = session.read_table("dim_customer")</div>
          <div className="text-red-700 bg-red-50 -mx-3 px-3">- conn = pyodbc.connect(DSN)</div>
          <div className="text-red-700 bg-red-50 -mx-3 px-3">- df = pd.read_sql("SELECT * …", conn)</div>
          <div className="mt-1">df = df.dropDuplicates(["id"])</div>
        </div>
        <div className="col-span-3 p-3 space-y-2 bg-soft-indigo/40">
          <div className="text-ink-4 text-[10.5px] uppercase tracking-wider">AI review</div>
          <div className="rounded-md bg-surface border border-hx p-2 text-ink-2">
            <div className="font-semibold text-[11px] text-emerald-700">Low risk</div>
            <div className="text-ink-3 mt-0.5">Migrated query uses session pool. Safe.</div>
          </div>
          <div className="rounded-md bg-surface border border-hx p-2 text-ink-2">
            <div className="font-semibold text-[11px] text-amber-700">Suggest</div>
            <div className="text-ink-3 mt-0.5">Add explicit schema for read_table.</div>
          </div>
        </div>
      </div>
    </div>
  );
}
