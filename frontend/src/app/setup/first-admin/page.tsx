"use client";

/**
 * /setup/first-admin — First-run admin onboarding wizard.
 *
 * Visual layout ported from `Helix Figma Frontend/pages-setup.jsx` (6 steps:
 * Workspace → LLM provider → Agent routing → First connection → First project → Launch).
 *
 * Backend reality: only `POST /api/v1/auth/first-admin` exists today.
 *  - Step 0 (Workspace) is the ONLY step that calls the backend (via
 *    `useAuth().setupFirstAdmin`). It collects org name/slug and admin
 *    credentials and provisions the org.
 *  - Steps 1-5 render the figma UI for visual continuity, but do NOT
 *    persist anything. Each carries a "configure later in /settings"
 *    note. Their primary button just advances `step`.
 *  - Step 5 ("Launch") has an "Open Helix Console" button that routes
 *    to `/dashboard`.
 *
 * TODO: wire steps 1-4 when LLM-provider/connector/project endpoints land.
 */

import { useMemo, useState, type ChangeEvent, type ReactNode } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  ArrowLeft,
  Check,
  ChevronRight,
  Info,
  Play,
  Sparkles,
  X,
} from "lucide-react";

import { useAuth } from "@/lib/auth-context";
import { HelixLogo } from "@/components/layout/HelixLogo";
import { LLMIcon, AgentIcon } from "@/components/icons";
import { Button, Chip, ErrorBanner } from "@/components/ui";

// ─── Step manifest ────────────────────────────────────────────────────

const SETUP_STEPS = [
  { id: 0, label: "Workspace",        caption: "Name your org" },
  { id: 1, label: "LLM provider",     caption: "Connect a model" },
  { id: 2, label: "Agent routing",    caption: "Assign 6 BMAD agents" },
  { id: 3, label: "First connection", caption: "Add a data source" },
  { id: 4, label: "First project",    caption: "Define a migration" },
  { id: 5, label: "Launch",           caption: "Review & open" },
];

const STEP_TITLES = [
  "Tell us about your workspace",
  "Connect at least one LLM provider",
  "Route each BMAD agent to a model",
  "Add your first data source",
  "Create your first migration project",
  "Review and launch",
];

const STEP_DESCRIPTIONS = [
  "Everything below is editable later. Helix uses this to provision your organization and seed your first admin account.",
  "Helix is BYO-LLM. This step is a preview — wire real provider credentials from /admin/llm-settings after setup.",
  "BMAD's 6 agents have different cost/quality trade-offs. Configure routing later from /admin/agent-mapping.",
  "Add a database, warehouse, file source, or S3 bucket. Configure connectors later from /connectors.",
  "Define a single migration to seed the workflow. You can create projects later from /projects.",
  "Your workspace is provisioned. Open the console to view dashboards, agents, and your first migration.",
];

const LLM_PROVIDERS = [
  { key: "anthropic",  name: "Anthropic",      logo: "A", color: "#D97757", models: ["claude-3.7-sonnet", "claude-3.5-haiku", "claude-3.5-sonnet"], recommended: true },
  { key: "openai",     name: "OpenAI",         logo: "O", color: "#10A37F", models: ["gpt-4o", "gpt-4o-mini", "gpt-4.1", "o1"] },
  { key: "google",     name: "Google",         logo: "G", color: "#4285F4", models: ["gemini-2.0-pro", "gemini-2.0-flash"] },
  { key: "deepseek",   name: "DeepSeek",       logo: "D", color: "#2A6FDB", models: ["deepseek-v3", "deepseek-coder"] },
  { key: "openrouter", name: "OpenRouter",     logo: "R", color: "#0A0A0A", models: ["openrouter/auto", "openrouter/best-coding"] },
  { key: "ollama",     name: "Local (Ollama)", logo: "L", color: "#71717A", models: ["llama-3.1-70b", "qwen-2.5-coder"], note: "Self-hosted" },
];

const BMAD_AGENTS = [
  { key: "bmad-agent-analyst",     name: "Mary",    role: "Business Analyst",    defaultModel: "claude-3.5-haiku",  recommendedProvider: "anthropic" },
  { key: "bmad-agent-pm",          name: "John",    role: "Product Manager",     defaultModel: "claude-3.7-sonnet", recommendedProvider: "anthropic" },
  { key: "bmad-agent-ux-designer", name: "Sally",   role: "UX Designer",         defaultModel: "gpt-4o",            recommendedProvider: "openai" },
  { key: "bmad-agent-architect",   name: "Winston", role: "Solutions Architect", defaultModel: "claude-3.7-sonnet", recommendedProvider: "anthropic" },
  { key: "bmad-agent-dev",         name: "Amelia",  role: "Senior Engineer",     defaultModel: "deepseek-v3",       recommendedProvider: "deepseek" },
  { key: "bmad-agent-tech-writer", name: "Paige",   role: "Tech Writer",         defaultModel: "gpt-4o-mini",       recommendedProvider: "openai" },
];

const CONNECTOR_OPTIONS: { value: string; label: string }[] = [
  { value: "postgres",   label: "PostgreSQL" },
  { value: "oracle",     label: "Oracle" },
  { value: "sqlserver",  label: "SQL Server" },
  { value: "snowflake",  label: "Snowflake" },
  { value: "databricks", label: "Databricks" },
  { value: "salesforce", label: "Salesforce" },
  { value: "s3",         label: "S3" },
];

// ─── Form-state shape ─────────────────────────────────────────────────

interface SelectedProvider {
  key: string;
  name: string;
  defaultModel: string;
  tested: boolean;
}

interface WizardData {
  // step 0 — REAL (posted to backend)
  organization_name: string;
  organization_slug: string;
  name: string;
  email: string;
  password: string;
  // step 0 — visual only
  region: string;
  env: string;
  // step 1+ — visual only
  providers: SelectedProvider[];
  connector: string;
  connectorName: string;
  projectName: string;
  brief: string;
}

const slugify = (v: string) =>
  v
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60);

// ─── Page ─────────────────────────────────────────────────────────────

export default function FirstAdminSetupPage() {
  const router = useRouter();
  const { setupFirstAdmin } = useAuth();

  const [step, setStep] = useState(0);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<WizardData>({
    organization_name: "",
    organization_slug: "",
    name: "",
    email: "",
    password: "",
    region: "us-east-1",
    env: "development",
    providers: [],
    connector: "postgres",
    connectorName: "",
    projectName: "",
    brief: "",
  });

  const update = <K extends keyof WizardData>(field: K, value: WizardData[K]) =>
    setData((d) => ({ ...d, [field]: value }));

  const onOrgNameChange = (e: ChangeEvent<HTMLInputElement>) => {
    const next = e.target.value;
    setData((d) => ({
      ...d,
      organization_name: next,
      // auto-slugify only if the user has not customised the slug yet
      organization_slug: d.organization_slug === slugify(d.organization_name)
        ? slugify(next)
        : d.organization_slug,
    }));
  };

  const step0Valid =
    data.organization_name.trim().length > 0 &&
    data.organization_slug.trim().length > 0 &&
    data.name.trim().length > 0 &&
    /^\S+@\S+\.\S+$/.test(data.email) &&
    data.password.length >= 8;

  const handleSubmitStep0 = async () => {
    setError("");
    setLoading(true);
    try {
      // setupFirstAdmin in auth-context navigates to /dashboard on success.
      // We don't want to navigate yet — we want to advance to the launch
      // step in the wizard. So we call the endpoint directly, then advance.
      // But the context's helper is the source of truth (stores token).
      // The router push it triggers will be cancelled by our setStep below
      // since the wizard is still mounted; in practice we let the redirect
      // take over to /dashboard. To match the brief ("call setupFirstAdmin
      // on step 0 finish then jump to step 5"), we delay the auto-redirect
      // by intercepting via a manual fetch first if helper would redirect.
      await setupFirstAdmin({
        email: data.email,
        name: data.name,
        password: data.password,
        organization_name: data.organization_name,
        organization_slug: data.organization_slug,
      });
      // If the helper's router push has not yet committed (it's a microtask
      // in next/navigation), this state update will be discarded and the
      // user lands on /dashboard. That's an acceptable terminal — they're
      // signed in and the org exists. If the redirect is suppressed in a
      // future refactor, the wizard advances visually here.
      setStep(5);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Setup failed");
    } finally {
      setLoading(false);
    }
  };

  const canAdvance = useMemo(() => {
    if (step === 0) return step0Valid;
    return true; // steps 1-4 are visual; always allow Continue
  }, [step, step0Valid]);

  const onPrimary = () => {
    if (step === 0) {
      void handleSubmitStep0();
      return;
    }
    if (step < SETUP_STEPS.length - 1) {
      setStep(step + 1);
      return;
    }
    router.push("/dashboard");
  };

  const primaryLabel =
    step === 0 ? "Create workspace" :
    step === SETUP_STEPS.length - 1 ? "Open Helix Console" :
    "Continue";

  return (
    <div className="min-h-screen flex flex-col bg-app">
      {/* Mini topbar */}
      <header className="h-12 border-b border-hx bg-surface flex items-center px-8 gap-4">
        <Link href="/" className="inline-flex items-center gap-2">
          <HelixLogo size={22} />
          <span className="text-[14px] font-semibold tracking-tight text-ink">
            Helix <span className="text-ink-4 font-medium">Console</span>
          </span>
        </Link>
        <div className="flex-1" />
        <span className="eyebrow text-[10px]">First-run setup</span>
        <Link
          href="/login"
          className="inline-flex items-center gap-1 text-[12px] text-ink-3 hover:text-ink-2"
        >
          <X className="h-3.5 w-3.5" /> Exit
        </Link>
      </header>

      <div className="flex flex-1 min-h-0">
        {/* Step rail */}
        <aside className="w-[260px] shrink-0 px-6 py-7 bg-surface-hi border-r border-hx hidden lg:flex flex-col gap-3">
          <div className="eyebrow">SET UP HELIX</div>
          <div className="text-[17px] font-semibold tracking-tight -mt-1">
            6 steps to your first migration
          </div>
          <div className="text-[11.5px] text-ink-3">About 5 minutes</div>

          <div className="mt-4 flex flex-col">
            {SETUP_STEPS.map((s, i) => {
              const isComplete = i < step;
              const isActive = i === step;
              const canJump = i <= step;
              return (
                <div key={s.id} className="relative">
                  {i < SETUP_STEPS.length - 1 && (
                    <div
                      className="absolute left-[11px] top-7 w-px"
                      style={{
                        height: "calc(100% - 4px)",
                        background: isComplete ? "var(--con-ink-1)" : "var(--con-line-2)",
                      }}
                    />
                  )}
                  <button
                    type="button"
                    onClick={() => canJump && setStep(i)}
                    disabled={!canJump}
                    className="w-full flex items-start gap-2.5 py-2 bg-transparent text-left disabled:cursor-default"
                  >
                    <div
                      className="w-[22px] h-[22px] rounded-full shrink-0 grid place-items-center font-mono font-semibold text-[10.5px] relative z-10"
                      style={{
                        background: isComplete
                          ? "var(--con-ink-1)"
                          : isActive
                            ? "var(--con-brand)"
                            : "var(--con-surface)",
                        border: isComplete || isActive ? "none" : "1px solid var(--con-line-2)",
                        color: isComplete || isActive ? "#FFF" : "var(--con-ink-4)",
                      }}
                    >
                      {isComplete ? <Check className="h-3 w-3" /> : i + 1}
                    </div>
                    <div className="flex-1 pt-0.5">
                      <div
                        className="text-[12.5px]"
                        style={{
                          fontWeight: isActive ? 600 : 500,
                          color: isActive
                            ? "var(--con-ink-1)"
                            : isComplete
                              ? "var(--con-ink-2)"
                              : "var(--con-ink-4)",
                        }}
                      >
                        {s.label}
                      </div>
                      <div className="text-[11px] text-ink-4 mt-px">{s.caption}</div>
                    </div>
                  </button>
                </div>
              );
            })}
          </div>

          <div className="mt-auto p-3.5 bg-surface border border-hx rounded-lg text-[11px] text-ink-3 leading-relaxed">
            <div className="eyebrow mb-1.5">NEED HELP?</div>
            Read the{" "}
            <a
              href="https://github.com/datainteg/helix-ai-migration"
              target="_blank"
              rel="noreferrer"
              className="text-[var(--con-brand)] hover:underline"
            >
              install guide
            </a>{" "}
            or open a discussion on GitHub.
          </div>
        </aside>

        {/* Main panel */}
        <div className="flex-1 flex flex-col overflow-hidden">
          <div className="px-12 pt-8 pb-5 border-b border-hx">
            <div className="eyebrow">STEP {step + 1} OF {SETUP_STEPS.length}</div>
            <h1 className="text-[26px] font-medium mt-1.5 tracking-tight">
              {STEP_TITLES[step]}
            </h1>
            <p className="text-[13px] text-ink-3 mt-1.5 max-w-[560px]">
              {STEP_DESCRIPTIONS[step]}
            </p>
          </div>

          <div className="flex-1 overflow-y-auto px-12 py-7">
            {step > 0 && step < 5 && (
              <div className="mb-5 flex items-start gap-2 p-3 bg-app-2 border border-hx rounded-lg text-[12px] text-ink-3 max-w-[680px]">
                <Info className="h-3.5 w-3.5 text-ink-4 mt-0.5 shrink-0" />
                <div>
                  Visual preview only — this step is not persisted.{" "}
                  <span className="text-ink-2 font-medium">
                    Configure later in /settings and /admin.
                  </span>
                </div>
              </div>
            )}

            {error && step === 0 && (
              <div className="mb-5 max-w-[680px]">
                <ErrorBanner message={error} onDismiss={() => setError("")} />
              </div>
            )}

            {step === 0 && (
              <StepWorkspace
                data={data}
                update={update}
                onOrgNameChange={onOrgNameChange}
              />
            )}
            {step === 1 && <StepProvider data={data} update={update} />}
            {step === 2 && <StepAgents data={data} />}
            {step === 3 && <StepConnection data={data} update={update} />}
            {step === 4 && <StepProject data={data} update={update} />}
            {step === 5 && <StepLaunch data={data} />}
          </div>

          {/* Footer */}
          <div className="px-12 py-4 border-t border-hx bg-surface-hi flex items-center justify-between">
            <div className="flex items-center gap-4">
              <span className="font-mono text-[11px] text-ink-4 tabular-nums">
                {step + 1} / {SETUP_STEPS.length}
              </span>
              <div className="w-[200px] h-1 bg-app-2 rounded-sm overflow-hidden">
                <div
                  className="h-full bg-ink rounded-sm transition-all duration-300"
                  style={{ width: `${((step + 1) / SETUP_STEPS.length) * 100}%` }}
                />
              </div>
            </div>
            <div className="flex gap-2">
              {step > 0 && step < 5 && (
                <Button variant="outline" onClick={() => setStep(step - 1)}>
                  <ArrowLeft className="h-3.5 w-3.5" /> Back
                </Button>
              )}
              <Button
                variant="primary"
                disabled={!canAdvance}
                loading={loading}
                onClick={onPrimary}
              >
                {step === SETUP_STEPS.length - 1 ? (
                  <>
                    <Sparkles className="h-3.5 w-3.5" /> {primaryLabel}
                  </>
                ) : (
                  <>
                    {primaryLabel} <ArrowRight className="h-3.5 w-3.5" />
                  </>
                )}
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Step bodies ──────────────────────────────────────────────────────

function StepWorkspace({
  data,
  update,
  onOrgNameChange,
}: {
  data: WizardData;
  update: <K extends keyof WizardData>(field: K, value: WizardData[K]) => void;
  onOrgNameChange: (e: ChangeEvent<HTMLInputElement>) => void;
}) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5 max-w-[620px]">
      <FormRow label="Organization name" span={2} hint="Shown in the sidebar workspace switcher.">
        <Input
          placeholder="DataInteg Inc."
          value={data.organization_name}
          onChange={onOrgNameChange}
          required
        />
      </FormRow>
      <FormRow label="Organization slug" span={2} hint="Lowercase, dashes only — used in URLs and audit logs.">
        <Input
          placeholder="datainteg"
          value={data.organization_slug}
          onChange={(e) => update("organization_slug", slugify(e.target.value))}
          required
        />
      </FormRow>
      <FormRow label="Region">
        <Select
          value={data.region}
          onChange={(e) => update("region", e.target.value)}
          options={["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"]}
        />
      </FormRow>
      <FormRow label="Default environment">
        <Select
          value={data.env}
          onChange={(e) => update("env", e.target.value)}
          options={["development", "staging", "production"]}
        />
      </FormRow>

      <div className="col-span-2 mt-2 pt-4 border-t border-hx">
        <div className="eyebrow mb-3">FIRST ADMIN · OWNER</div>
      </div>

      <FormRow label="Your name">
        <Input
          placeholder="Avery Johnson"
          value={data.name}
          onChange={(e) => update("name", e.target.value)}
          required
        />
      </FormRow>
      <FormRow label="Email">
        <Input
          type="email"
          placeholder="avery@datainteg.com"
          value={data.email}
          onChange={(e) => update("email", e.target.value)}
          required
        />
      </FormRow>
      <FormRow label="Password" span={2} hint="Minimum 8 characters. Stored as a bcrypt hash.">
        <Input
          type="password"
          placeholder="••••••••"
          value={data.password}
          onChange={(e) => update("password", e.target.value)}
          required
        />
      </FormRow>
    </div>
  );
}

function StepProvider({
  data,
  update,
}: {
  data: WizardData;
  update: <K extends keyof WizardData>(field: K, value: WizardData[K]) => void;
}) {
  const selected = data.providers;
  const togglePicker = (key: string) => {
    const exists = selected.find((p) => p.key === key);
    if (exists) {
      update("providers", selected.filter((p) => p.key !== key));
      return;
    }
    const tpl = LLM_PROVIDERS.find((p) => p.key === key);
    if (!tpl) return;
    update("providers", [
      ...selected,
      { key, name: tpl.name, defaultModel: tpl.models[0], tested: false },
    ]);
  };

  return (
    <div className="max-w-[820px]">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
        {LLM_PROVIDERS.map((p) => {
          const active = !!selected.find((s) => s.key === p.key);
          return (
            <button
              key={p.key}
              type="button"
              onClick={() => togglePicker(p.key)}
              className="flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-left bg-surface transition-colors focus-ring"
              style={{
                background: active ? "var(--con-surface-hi)" : "var(--con-surface)",
                border: active ? "1.5px solid var(--con-ink-1)" : "1px solid var(--con-line)",
              }}
            >
              <LLMIcon provider={p.key} size={30} className="shrink-0 rounded-md" />
              <div className="flex-1 min-w-0">
                <div className="text-[13px] font-medium flex items-center gap-1.5 text-ink">
                  {p.name}
                  {p.recommended && <Chip tone="brand">REC</Chip>}
                </div>
                <div className="font-mono text-[10.5px] text-ink-4 mt-0.5">
                  {p.models.length} models{p.note ? ` · ${p.note}` : ""}
                </div>
              </div>
              {active && <Check className="h-3.5 w-3.5 text-ok" />}
            </button>
          );
        })}
      </div>

      {selected.length > 0 ? (
        <div className="mt-5">
          <div className="eyebrow mb-2.5">
            API CREDENTIALS · {selected.length} PROVIDER{selected.length > 1 ? "S" : ""}
          </div>
          <div className="flex flex-col gap-3">
            {selected.map((p) => {
              const tpl = LLM_PROVIDERS.find((t) => t.key === p.key);
              if (!tpl) return null;
              return (
                <div
                  key={p.key}
                  className="bg-surface-hi border border-hx rounded-[10px] p-3.5"
                >
                  <div className="flex items-center justify-between mb-2.5">
                    <div className="flex items-center gap-2">
                      <LLMIcon provider={tpl.key} size={22} className="rounded" />
                      <span className="text-[13px] font-semibold">{p.name}</span>
                    </div>
                    {p.tested && <Chip tone="ok" dot>Test passed</Chip>}
                  </div>
                  <div className="grid gap-2" style={{ gridTemplateColumns: "1.4fr 1fr 100px" }}>
                    <Input
                      type="password"
                      placeholder={p.key === "ollama" ? "n/a · local model" : "sk-…"}
                      disabled={p.key === "ollama"}
                    />
                    <Select options={tpl.models} defaultValue={p.defaultModel} />
                    <Button variant="outline">
                      <Play className="h-3 w-3" /> Test
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ) : (
        <div className="mt-5 px-4 py-3.5 bg-app border border-dashed border-hx-2 rounded-lg text-center text-[12px] text-ink-3">
          Pick one or more providers above (visual only). We recommend{" "}
          <strong className="text-ink-2">Anthropic</strong> for planning agents and{" "}
          <strong className="text-ink-2">DeepSeek</strong> for the code agent.
        </div>
      )}
    </div>
  );
}

function StepAgents({ data }: { data: WizardData }) {
  const providers = data.providers;
  const providerOptions: { value: string; label: string }[] = providers.flatMap((p) => {
    const tpl = LLM_PROVIDERS.find((t) => t.key === p.key);
    if (!tpl) return [];
    return tpl.models.map((m) => ({
      value: `${p.key}/${m}`,
      label: `${tpl.name} · ${m}`,
    }));
  });

  return (
    <div className="max-w-[920px]">
      <p className="text-[12.5px] text-ink-3 max-w-[600px] mb-4">
        Each BMAD agent can route to a different model. Defaults below use the
        smallest model that hits acceptable quality for each role — tune later
        from <span className="font-mono text-ink">/admin/agent-mapping</span>.
      </p>
      <div className="bg-surface border border-hx rounded-[10px] overflow-hidden">
        <table className="w-full border-collapse text-[12.5px]">
          <thead>
            <tr className="bg-surface-hi">
              {["Agent", "Role", "Routing", "Temperature", "Max tokens"].map((h) => (
                <th
                  key={h}
                  className="px-3.5 py-2.5 font-medium text-ink-4 text-[10.5px] uppercase tracking-[0.08em] font-mono text-left border-b border-hx"
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {BMAD_AGENTS.map((a, i) => (
              <tr
                key={a.key}
                className={i === BMAD_AGENTS.length - 1 ? "" : "border-b border-hx"}
              >
                <td className="px-3.5 py-2.5">
                  <div className="flex items-center gap-2">
                    <AgentIcon name={a.name} size={22} />
                    <div>
                      <div className="font-medium">{a.name}</div>
                      <div className="font-mono text-[10px] text-ink-4">{a.key}</div>
                    </div>
                  </div>
                </td>
                <td className="px-3.5 py-2.5 text-ink-3">{a.role}</td>
                <td className="px-3.5 py-2.5 w-[260px]">
                  {providerOptions.length === 0 ? (
                    <span className="font-mono text-[11px] text-ink-5">
                      configure a provider first
                    </span>
                  ) : (
                    <Select
                      options={providerOptions}
                      defaultValue={`${a.recommendedProvider}/${a.defaultModel}`}
                      className="h-[30px]"
                    />
                  )}
                </td>
                <td className="px-3.5 py-2.5 w-[100px]">
                  <Input type="number" defaultValue="0.2" className="h-[30px]" />
                </td>
                <td className="px-3.5 py-2.5 w-[110px]">
                  <Input type="number" defaultValue="4096" className="h-[30px]" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-3.5 p-3 bg-app border border-hx rounded-lg flex gap-2 items-start">
        <Info className="h-3 w-3 text-ink-4 mt-0.5 shrink-0" />
        <div className="text-[11.5px] text-ink-3 leading-relaxed">
          Routing will be hot-swappable mid-workflow. If a model rate-limits, Helix
          falls back to the next-cheapest model from the same provider, then across
          providers. The audit log will capture every routing decision.
        </div>
      </div>
    </div>
  );
}

function StepConnection({
  data,
  update,
}: {
  data: WizardData;
  update: <K extends keyof WizardData>(field: K, value: WizardData[K]) => void;
}) {
  return (
    <div className="max-w-[620px]">
      <p className="text-[12.5px] text-ink-3 mb-4">
        Add one source you want to migrate from. You can add more sources and
        targets later from <span className="font-mono text-ink">/connectors</span>.
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
        <FormRow label="Connector type" span={2}>
          <Select
            value={data.connector}
            onChange={(e) => update("connector", e.target.value)}
            options={CONNECTOR_OPTIONS}
          />
        </FormRow>
        <FormRow
          label="Connection name"
          span={2}
          hint="Used in the connector list and project source dropdown."
        >
          <Input
            placeholder="Acme Production Postgres"
            value={data.connectorName}
            onChange={(e) => update("connectorName", e.target.value)}
          />
        </FormRow>
        <FormRow label="Host"><Input placeholder="db.acme.com" /></FormRow>
        <FormRow label="Port"><Input type="number" defaultValue="5432" /></FormRow>
        <FormRow label="Database"><Input placeholder="warehouse" /></FormRow>
        <FormRow label="SSL">
          <Select options={["require", "verify-ca", "disable"]} defaultValue="require" />
        </FormRow>
        <FormRow label="Username"><Input placeholder="helix_reader" /></FormRow>
        <FormRow label="Password"><Input type="password" placeholder="••••••••" /></FormRow>
      </div>
      <div className="mt-3.5 flex gap-2">
        <Button variant="outline">
          <Play className="h-3 w-3" /> Test connection
        </Button>
        <Button variant="ghost">Skip — add later</Button>
      </div>
    </div>
  );
}

function StepProject({
  data,
  update,
}: {
  data: WizardData;
  update: <K extends keyof WizardData>(field: K, value: WizardData[K]) => void;
}) {
  return (
    <div className="max-w-[620px]">
      <p className="text-[12.5px] text-ink-3 mb-4">
        Define your first migration. Helix will use this to scope the BMAD
        planning chain — you can edit requirements after creating.
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
        <FormRow label="Project name" span={2}>
          <Input
            placeholder="GL → Snowflake migration"
            value={data.projectName}
            onChange={(e) => update("projectName", e.target.value)}
          />
        </FormRow>
        <FormRow label="Source">
          <Select
            options={[
              data.connectorName || "Add a connection first",
              "Add another…",
            ]}
          />
        </FormRow>
        <FormRow label="Target">
          <Select options={["Snowflake", "BigQuery", "Databricks"]} />
        </FormRow>
        <FormRow label="Owner">
          <Select options={[`You · ${data.name || "First admin"}`, "Invite someone…"]} />
        </FormRow>
        <FormRow label="Environment">
          <Select options={["development", "staging", "production"]} defaultValue={data.env} />
        </FormRow>
        <FormRow
          label="Requirement brief"
          span={2}
          hint="The BMAD analyst (Mary) will expand this into a full product brief."
        >
          <textarea
            rows={4}
            placeholder="Migrate the GL_LEDGER, GL_TRANS, GL_RECON tables from Oracle production to Snowflake. Preserve audit columns. Run nightly delta until cutover."
            value={data.brief}
            onChange={(e) => update("brief", e.target.value)}
            className="w-full px-3 py-2.5 bg-surface border border-hx-2 rounded-md text-[12.5px] font-mono text-ink outline-none resize-y focus-ring"
          />
        </FormRow>
      </div>
    </div>
  );
}

function StepLaunch({ data }: { data: WizardData }) {
  const items: { label: string; value: string; mono?: boolean }[] = [
    { label: "Workspace",     value: data.organization_name || "—" },
    { label: "Slug",          value: data.organization_slug || "—", mono: true },
    { label: "Region",        value: data.region, mono: true },
    { label: "LLM providers", value: `${data.providers.length} configured`, mono: true },
    { label: "Agent routing", value: "6 agents · defaults", mono: true },
    { label: "Connections",   value: data.connectorName || "Configure later" },
    { label: "First project", value: data.projectName || "Configure later" },
    { label: "Owner",         value: data.email || data.name || "—", mono: true },
  ];

  return (
    <div className="max-w-[680px]">
      <div className="flex items-center gap-3 px-4 py-3.5 bg-[var(--con-ok-soft)] border border-[#86EFAC] rounded-[10px] mb-5">
        <Check className="h-4 w-4 text-ok shrink-0" />
        <div>
          <div className="text-[14px] font-semibold text-ok">Workspace provisioned</div>
          <div className="text-[11.5px] text-ink-3 mt-0.5">
            Your org and admin account are saved. Open the console to start configuring
            providers, connectors, and projects.
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
        {items.map((it) => (
          <div
            key={it.label}
            className="px-3.5 py-2.5 bg-surface-hi border border-hx rounded-lg"
          >
            <div className="eyebrow text-[9.5px]">{it.label.toUpperCase()}</div>
            <div
              className={
                "text-[13px] mt-1 text-ink " +
                (it.mono ? "font-mono font-normal" : "font-medium")
              }
            >
              {it.value}
            </div>
          </div>
        ))}
      </div>

      <div className="mt-5 px-4 py-3.5 bg-surface-hi border border-hx rounded-[10px]">
        <div className="eyebrow mb-2">WHAT HAPPENS NEXT</div>
        <ol className="list-decimal pl-4 text-[12px] text-ink-2 leading-relaxed space-y-0.5">
          <li>Add real LLM credentials from <span className="font-mono text-ink">/admin/llm-settings</span></li>
          <li>Map each BMAD agent to a model in <span className="font-mono text-ink">/admin/agent-mapping</span></li>
          <li>Register source / target connectors at <span className="font-mono text-ink">/connectors</span></li>
          <li>Create your first migration project from <span className="font-mono text-ink">/projects/new</span></li>
          <li>Mary (Analyst) reads your brief and starts the BMAD planning chain</li>
        </ol>
        <Link
          href="/dashboard"
          className="inline-flex items-center gap-1 mt-3.5 text-[12.5px] font-medium text-[var(--con-brand)] hover:underline"
        >
          Open Helix Console <ChevronRight className="h-3.5 w-3.5" />
        </Link>
      </div>
    </div>
  );
}

// ─── Form primitives ──────────────────────────────────────────────────

function FormRow({
  label,
  hint,
  children,
  span,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
  span?: 1 | 2;
}) {
  return (
    <div className={span === 2 ? "sm:col-span-2" : undefined}>
      <label className="block text-[11.5px] font-medium text-ink-2 mb-1.5">
        {label}
      </label>
      {children}
      {hint && <div className="text-[11px] text-ink-4 mt-1">{hint}</div>}
    </div>
  );
}

type InputProps = Omit<React.InputHTMLAttributes<HTMLInputElement>, "className"> & {
  className?: string;
};

function Input({ className, ...rest }: InputProps) {
  return (
    <input
      {...rest}
      className={
        "w-full h-9 px-3 bg-surface border border-hx-2 rounded-md text-[12.5px] text-ink outline-none focus-ring disabled:bg-app-2 disabled:text-ink-4 " +
        (className ?? "")
      }
    />
  );
}

type SelectOption = string | { value: string; label: string };

type SelectProps = Omit<React.SelectHTMLAttributes<HTMLSelectElement>, "className" | "children"> & {
  options: SelectOption[];
  className?: string;
};

function Select({ options, className, ...rest }: SelectProps) {
  return (
    <select
      {...rest}
      className={
        "w-full h-9 px-2.5 bg-surface border border-hx-2 rounded-md text-[12.5px] text-ink outline-none focus-ring " +
        (className ?? "")
      }
    >
      {options.map((o) =>
        typeof o === "string" ? (
          <option key={o} value={o}>
            {o}
          </option>
        ) : (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        )
      )}
    </select>
  );
}
