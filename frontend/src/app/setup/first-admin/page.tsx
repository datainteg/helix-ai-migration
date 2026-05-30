"use client";

/**
 * /setup/first-admin — First-run admin onboarding wizard.
 *
 * Visual layout ported from `Helix Figma Frontend/pages-setup.jsx` (6 steps:
 * Workspace → LLM provider → Agent routing → First connection → First project → Launch).
 *
 * Every step now persists to the backend:
 *  - Step 0 (Workspace)      → POST /api/v1/auth/first-admin (provisions org + admin,
 *                              returns access_token used for steps 1-4).
 *  - Step 1 (LLM provider)   → POST /api/v1/llm-providers for each selected provider.
 *                              Provider IDs are captured for the routing step.
 *  - Step 2 (Agent routing)  → PUT  /api/v1/llm-agent-mappings (atomic replace) with
 *                              the 6 BMAD agents → provider/model pairs.
 *  - Step 3 (First connection) — collected locally only; persisted in step 4 once a
 *                              project exists (sources are project-scoped).
 *  - Step 4 (First project)  → POST /api/v1/projects then, if step 3 was filled,
 *                              POST /api/v1/projects/{id}/sources.
 *  - Step 5 (Launch)         → review screen with real IDs; "Open Helix Console" → /dashboard.
 *
 * Auth note: step 0 calls the first-admin endpoint directly (not the auth-context
 * helper) because the helper unconditionally pushes to /dashboard on success. We
 * still store the token in localStorage so other parts of the app pick it up.
 */

import React, { useEffect, useId, useMemo, useState, type ChangeEvent, type ReactNode } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
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

import { HelixLogo } from "@/components/layout/HelixLogo";
import { LLMIcon, AgentIcon } from "@/components/icons";
import { Button, Chip, ErrorBanner } from "@/components/ui";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

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
  "Helix is BYO-LLM. Pick one or more providers, paste the API key, and we'll persist them to /admin/llm-settings.",
  "BMAD's 6 agents have different cost/quality trade-offs. Set defaults now — change later from /admin/agent-mapping.",
  "Add a database, warehouse, file source, or S3 bucket. The connection is saved once you create the project in the next step.",
  "Define a single migration to seed the workflow. You can create more projects later from /projects.",
  "Your workspace is provisioned. Open the console to view dashboards, agents, and your first migration.",
];

const LLM_PROVIDERS = [
  { key: "anthropic",  name: "Anthropic",          logo: "A", color: "#D97757", models: ["claude-opus-4-7", "claude-sonnet-4-6", "claude-haiku-4-5"], recommended: true },
  { key: "openai",     name: "OpenAI",             logo: "O", color: "#10A37F", models: ["gpt-5.5", "gpt-5-mini", "gpt-5.5-thinking", "gpt-realtime-2"] },
  { key: "google",     name: "Google (Gemini API)", logo: "G", color: "#4285F4", models: ["gemini-3-pro", "gemini-3-flash", "gemini-3.1-flash-lite", "gemini-omni"] },
  { key: "deepseek",   name: "DeepSeek",           logo: "D", color: "#5786FE", models: ["deepseek-v4-pro", "deepseek-v4-flash"] },
  { key: "openrouter", name: "OpenRouter",         logo: "R", color: "#0A0A0A", models: ["openai/gpt-5.5", "anthropic/claude-opus-4.7", "google/gemini-3-pro", "deepseek/deepseek-v4-pro"] },
  { key: "bedrock",    name: "AWS Bedrock",        logo: "B", color: "#FF9900", models: ["anthropic.claude-opus-4-7", "anthropic.claude-sonnet-4-6", "openai.gpt-5.5", "meta.llama4-maverick", "mistral.mistral-large", "amazon.titan-text-premier-v1", "cohere.command-r-plus-v1", "deepseek.deepseek-v4"], note: "AWS auth via region + access keys (or IAM role)" },
  { key: "vertex",     name: "Google Vertex AI",   logo: "V", color: "#4285F4", models: ["gemini-3-pro", "gemini-3-flash", "gemini-omni", "imagen-4", "veo-3"], note: "Requires GCP project + ADC" },
  { key: "azure",      name: "Azure OpenAI",       logo: "A", color: "#0078D4", models: ["gpt-5.5", "gpt-5-mini", "o1", "phi-4"], note: "Requires endpoint + deployment name" },
  { key: "local",      name: "Local (Ollama / LM Studio)", logo: "L", color: "#71717A", models: ["llama4", "qwen3", "gemma3", "mistral-large"], note: "Self-hosted" },
  { key: "custom",     name: "Custom OpenAI-compatible", logo: "C", color: "#52525B", models: [], note: "vLLM, Together, Fireworks, Groq, Cerebras, ..." },
];

const KEYLESS_PROVIDERS = new Set(["bedrock", "vertex", "local"]);

const BMAD_AGENTS = [
  { key: "bmad-agent-analyst",     name: "Mary",    role: "Business Analyst",    defaultModel: "claude-haiku-4-5",  recommendedProvider: "anthropic" },
  { key: "bmad-agent-pm",          name: "John",    role: "Product Manager",     defaultModel: "claude-sonnet-4-6", recommendedProvider: "anthropic" },
  { key: "bmad-agent-ux-designer", name: "Sally",   role: "UX Designer",         defaultModel: "gpt-5.5",           recommendedProvider: "openai" },
  { key: "bmad-agent-architect",   name: "Winston", role: "Solutions Architect", defaultModel: "claude-opus-4-7",   recommendedProvider: "anthropic" },
  { key: "bmad-agent-dev",         name: "Amelia",  role: "Senior Engineer",     defaultModel: "deepseek-v4-pro",   recommendedProvider: "deepseek" },
  { key: "bmad-agent-tech-writer", name: "Paige",   role: "Tech Writer",         defaultModel: "gpt-5-mini",        recommendedProvider: "openai" },
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

const TARGET_OPTIONS: { value: string; label: string }[] = [
  { value: "snowflake",  label: "Snowflake" },
  { value: "bigquery",   label: "BigQuery" },
  { value: "databricks", label: "Databricks" },
  { value: "postgres",   label: "PostgreSQL" },
];

// ─── Form-state shape ─────────────────────────────────────────────────

interface SelectedProvider {
  key: string;            // provider_type (anthropic, openai, …)
  name: string;
  apiKey: string;
  defaultModel: string;
  baseUrl: string;
  /** Populated after step 1 POSTs to /llm-providers — used by step 2 mappings. */
  providerId?: string;
}

interface AgentRouting {
  agentKey: string;       // e.g. bmad-agent-analyst
  providerKey: string;    // refers to SelectedProvider.key (provider_type)
  model: string;
  temperature: number;
  maxTokens: number;
}

interface ConnectionDraft {
  type: string;           // connector_type (postgres, oracle, …)
  name: string;
  host: string;
  port: string;
  database: string;
  username: string;
  password: string;
  ssl: string;
}

interface ProjectDraft {
  name: string;
  brief: string;
  target: string;
  environment: string;
}

interface WizardData {
  // step 0
  organization_name: string;
  organization_slug: string;
  name: string;
  email: string;
  password: string;
  setup_token: string;
  region: string;
  env: string;
  // step 1
  providers: SelectedProvider[];
  // step 2
  agents: AgentRouting[];
  // step 3
  connection: ConnectionDraft;
  // step 4
  project: ProjectDraft;
}

interface PersistedIds {
  token?: string;
  providerIds: Record<string, string>;     // providerKey → backend id
  mappingsSaved: boolean;
  projectId?: string;
  sourceConnectionId?: string;
}

const slugify = (v: string) =>
  v
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60);

const emptyConnection: ConnectionDraft = {
  type: "postgres",
  name: "",
  host: "",
  port: "5432",
  database: "",
  username: "",
  password: "",
  ssl: "require",
};

const emptyProject: ProjectDraft = {
  name: "",
  brief: "",
  target: "snowflake",
  environment: "development",
};

// ─── Page ─────────────────────────────────────────────────────────────

export default function FirstAdminSetupPage() {
  const router = useRouter();
  const { setSession } = useAuth();

  const [step, setStep] = useState(0);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [persisted, setPersisted] = useState<PersistedIds>({
    providerIds: {},
    mappingsSaved: false,
  });
  const [data, setData] = useState<WizardData>({
    organization_name: "",
    organization_slug: "",
    name: "",
    email: "",
    password: "",
    setup_token: "",
    region: "us-east-1",
    env: "development",
    providers: [],
    agents: [],
    connection: { ...emptyConnection },
    project: { ...emptyProject },
  });

  const update = <K extends keyof WizardData>(field: K, value: WizardData[K]) =>
    setData((d) => ({ ...d, [field]: value }));

  // UI-024 — persist the wizard step + non-secret draft to sessionStorage so an
  // accidental reload mid-flow doesn't drop the operator back to step 0. We
  // deliberately strip secrets (admin password, setup token, connection
  // password) from the draft — those are re-entered after a reload rather than
  // sitting in sessionStorage in plaintext.
  const DRAFT_KEY = "helix.first-admin.draft.v1";
  const [draftRestored, setDraftRestored] = useState(false);

  useEffect(() => {
    try {
      const raw = sessionStorage.getItem(DRAFT_KEY);
      if (raw) {
        const saved = JSON.parse(raw) as { step?: number; data?: Partial<WizardData> };
        if (saved.data) {
          setData((d) => ({
            ...d,
            ...saved.data,
            // never trust persisted secrets
            password: "",
            setup_token: "",
            connection: { ...d.connection, ...(saved.data?.connection ?? {}), password: "" },
            project: { ...d.project, ...(saved.data?.project ?? {}) },
          }));
        }
        if (typeof saved.step === "number") setStep(saved.step);
      }
    } catch {
      /* corrupt draft — ignore and start fresh */
    }
    setDraftRestored(true);
    // run once on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!draftRestored) return; // don't clobber the saved draft before restore
    try {
      const { password: _pw, setup_token: _st, connection, ...rest } = data;
      const safeConnection = { ...connection, password: "" };
      sessionStorage.setItem(
        DRAFT_KEY,
        JSON.stringify({ step, data: { ...rest, connection: safeConnection } })
      );
    } catch {
      /* storage full / unavailable — non-fatal */
    }
  }, [step, data, draftRestored]);

  const onOrgNameChange = (e: ChangeEvent<HTMLInputElement>) => {
    const next = e.target.value;
    setData((d) => ({
      ...d,
      organization_name: next,
      organization_slug: d.organization_slug === slugify(d.organization_name)
        ? slugify(next)
        : d.organization_slug,
    }));
  };

  // Whenever the selected providers change, prune / refresh the agent routing rows
  // so each agent always points at a still-selected provider.
  useEffect(() => {
    if (data.providers.length === 0) {
      if (data.agents.length > 0) update("agents", []);
      return;
    }
    const byKey: Record<string, SelectedProvider> = {};
    data.providers.forEach((p) => { byKey[p.key] = p; });

    const next: AgentRouting[] = BMAD_AGENTS.map((a) => {
      const existing = data.agents.find((row) => row.agentKey === a.key);
      // Prefer existing choice if its provider is still selected
      if (existing && byKey[existing.providerKey]) {
        const tpl = LLM_PROVIDERS.find((p) => p.key === existing.providerKey)!;
        const model = tpl.models.includes(existing.model)
          ? existing.model
          : (byKey[existing.providerKey].defaultModel || tpl.models[0] || existing.model);
        return { ...existing, model };
      }
      // Otherwise prefer recommendedProvider if selected, else first selected
      const preferred = byKey[a.recommendedProvider] ?? data.providers[0];
      const tpl = LLM_PROVIDERS.find((p) => p.key === preferred.key)!;
      const model = tpl.models.includes(a.defaultModel)
        ? a.defaultModel
        : (preferred.defaultModel || tpl.models[0] || a.defaultModel);
      return {
        agentKey: a.key,
        providerKey: preferred.key,
        model,
        temperature: 0.2,
        maxTokens: 4096,
      };
    });
    update("agents", next);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data.providers.map((p) => p.key).join("|")]);

  // ─── Step validators ───────────────────────────────────────────────

  const step0Valid =
    data.organization_name.trim().length > 0 &&
    data.organization_slug.trim().length > 0 &&
    data.name.trim().length > 0 &&
    /^\S+@\S+\.\S+$/.test(data.email) &&
    // SC-002: backend password policy requires min 12 chars + complexity.
    data.password.length >= 12 &&
    // SC-011: setup token is mandatory for the first-admin bootstrap.
    data.setup_token.trim().length > 0;

  const step1Valid =
    data.providers.length > 0 &&
    data.providers.every((p) => KEYLESS_PROVIDERS.has(p.key) || p.apiKey.trim().length > 0);

  const step2Valid =
    data.agents.length === BMAD_AGENTS.length &&
    data.agents.every((row) => row.providerKey && row.model);

  // Step 3 is optional; if the user fills the name we require a host
  const step3Valid =
    !data.connection.name.trim() ||
    (data.connection.host.trim().length > 0 && data.connection.name.trim().length > 0);

  const step4Valid = data.project.name.trim().length > 0;

  // ─── Persistence handlers ──────────────────────────────────────────

  const persistStep0 = async () => {
    const res = await fetch(`${API_BASE}/api/v1/auth/first-admin`, {
      method: "POST",
      // SC-010: receive the HttpOnly cookie the backend sets on success so the
      // subsequent wizard steps authenticate via the cookie.
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        // SC-011: the backend requires an out-of-band setup token (printed to
        // the backend logs on first boot) to defeat the bootstrap race.
        "X-Setup-Token": data.setup_token.trim(),
      },
      body: JSON.stringify({
        email: data.email,
        name: data.name,
        password: data.password,
        organization_name: data.organization_name,
        organization_slug: data.organization_slug,
      }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || "Workspace setup failed");
    }
    const body = (await res.json()) as { access_token: string };
    // Use AuthContext so token state stays in sync with the rest of the app;
    // setSession persists to localStorage internally. Do NOT redirect — the
    // wizard owns navigation flow.
    setSession(body.access_token, { email: data.email, name: data.name });
    setPersisted((p) => ({ ...p, token: body.access_token }));
  };

  const persistStep1 = async () => {
    const token = persisted.token;
    if (!token) throw new Error("Missing auth token — restart at step 1");
    const ids: Record<string, string> = { ...persisted.providerIds };
    const updatedProviders: SelectedProvider[] = [];

    for (const p of data.providers) {
      if (ids[p.key]) {
        // Already created in a previous attempt — reuse the id.
        updatedProviders.push({ ...p, providerId: ids[p.key] });
        continue;
      }
      const res = await fetch(`${API_BASE}/api/v1/llm-providers`, {
        method: "POST",
        credentials: "include", // SC-010: auth via HttpOnly cookie
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          provider_type: p.key,
          name: p.name,
          api_key: p.apiKey || "",
          base_url: p.baseUrl || undefined,
          default_model: p.defaultModel,
        }),
      });
      if (!res.ok) {
        // Persist whatever succeeded BEFORE this failure so retry skips them.
        // (Previously setPersisted only ran after the full loop — a mid-loop
        // throw lost every just-created id.)
        setPersisted((s) => ({ ...s, providerIds: ids }));
        const body = await res.json().catch(() => ({}));
        throw new Error(`Failed to save provider "${p.name}": ${body.detail || res.statusText}`);
      }
      const created = (await res.json()) as { id: string };
      ids[p.key] = created.id;
      updatedProviders.push({ ...p, providerId: created.id });
      // Save incrementally so a later failure doesn't strand earlier wins.
      setPersisted((s) => ({ ...s, providerIds: { ...ids } }));
    }
    update("providers", updatedProviders);
  };

  const persistStep2 = async () => {
    const token = persisted.token;
    if (!token) throw new Error("Missing auth token");
    const payload = data.agents
      .map((row) => {
        const providerId = persisted.providerIds[row.providerKey];
        if (!providerId) return null;
        return {
          agent_type: row.agentKey,
          provider_id: providerId,
          model: row.model,
          temperature: row.temperature,
          max_tokens: row.maxTokens,
        };
      })
      .filter((x): x is NonNullable<typeof x> => x !== null);

    if (payload.length !== BMAD_AGENTS.length) {
      throw new Error("Each BMAD agent needs a provider — go back and review step 1.");
    }
    const res = await fetch(`${API_BASE}/api/v1/llm-agent-mappings`, {
      method: "PUT",
      credentials: "include", // SC-010: auth via HttpOnly cookie
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(`Failed to save agent routing: ${body.detail || res.statusText}`);
    }
    setPersisted((s) => ({ ...s, mappingsSaved: true }));
  };

  const persistStep4 = async () => {
    const token = persisted.token;
    if (!token) throw new Error("Missing auth token");

    // 1) Create the project.
    let projectId = persisted.projectId;
    if (!projectId) {
      const res = await fetch(`${API_BASE}/api/v1/projects`, {
        method: "POST",
        credentials: "include", // SC-010: auth via HttpOnly cookie
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: data.project.name,
          description: data.project.brief || `Migration → ${data.project.target}`,
          migration_type: `${data.connection.type || "source"} → ${data.project.target}`,
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(`Failed to create project: ${body.detail || res.statusText}`);
      }
      const project = (await res.json()) as { id: string };
      projectId = project.id;
      setPersisted((s) => ({ ...s, projectId }));
    }

    // 2) If the user filled in a source connection in step 3, persist it now.
    if (data.connection.name.trim() && !persisted.sourceConnectionId) {
      const config: Record<string, string | number> = {};
      const c = data.connection;
      if (c.host) config.host = c.host;
      if (c.port) config.port = Number(c.port) || c.port;
      if (c.database) config.database = c.database;
      if (c.username) config.username = c.username;
      if (c.password) config.password = c.password;
      if (c.ssl) config.ssl = c.ssl;

      const res = await fetch(`${API_BASE}/api/v1/projects/${projectId}/sources`, {
        method: "POST",
        credentials: "include", // SC-010: auth via HttpOnly cookie
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: c.name,
          connector_type: c.type,
          config,
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(`Project created, but source connection failed: ${body.detail || res.statusText}`);
      }
      const src = (await res.json()) as { id: string };
      setPersisted((s) => ({ ...s, sourceConnectionId: src.id }));
    }
  };

  // ─── Step button orchestration ────────────────────────────────────

  const stepValidity = [step0Valid, step1Valid, step2Valid, step3Valid, step4Valid, true];
  const canAdvance = stepValidity[step];

  const onPrimary = async () => {
    setError("");
    if (step === SETUP_STEPS.length - 1) {
      // Setup finished — drop the saved draft so a future visit starts clean (UI-024).
      try { sessionStorage.removeItem(DRAFT_KEY); } catch { /* ignore */ }
      router.push("/dashboard");
      return;
    }
    setLoading(true);
    try {
      if (step === 0) await persistStep0();
      else if (step === 1) await persistStep1();
      else if (step === 2) await persistStep2();
      else if (step === 4) await persistStep4();
      // step 3 has nothing to POST yet (no project) — pure local capture.
      setStep((s) => s + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Step failed");
    } finally {
      setLoading(false);
    }
  };

  const primaryLabel =
    step === 0 ? "Create workspace" :
    step === 1 ? "Save providers" :
    step === 2 ? "Save routing" :
    step === 3 ? (data.connection.name.trim() ? "Continue" : "Skip — add later") :
    step === 4 ? "Create project" :
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
                    aria-current={isActive ? "step" : undefined}
                    className="w-full flex items-start gap-2.5 py-2 bg-transparent text-left disabled:cursor-default focus-ring"
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
            {/* Step 3 alone remains optional — keep its banner.
                Steps 1/2/4 now persist; no banner needed. */}
            {step === 3 && (
              <div className="mb-5 flex items-start gap-2 p-3 bg-app-2 border border-hx rounded-lg text-[12px] text-ink-3 max-w-[680px]">
                <Info className="h-3.5 w-3.5 text-ink-4 mt-0.5 shrink-0" />
                <div>
                  Optional — leave name blank to skip. The connection is saved when you
                  create the project in the next step (sources are project-scoped).
                </div>
              </div>
            )}

            {error && (
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
            {step === 2 && <StepAgents data={data} update={update} />}
            {step === 3 && <StepConnection data={data} update={update} />}
            {step === 4 && <StepProject data={data} update={update} />}
            {step === 5 && <StepLaunch data={data} persisted={persisted} />}
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
                disabled={!canAdvance || loading}
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
      <FormRow
        label="Password"
        span={2}
        hint="Minimum 12 characters with upper + lower case, a digit, and a symbol. Stored as a bcrypt hash."
      >
        <Input
          type="password"
          placeholder="••••••••••••"
          value={data.password}
          onChange={(e) => update("password", e.target.value)}
          required
        />
      </FormRow>
      <FormRow
        label="Setup token"
        span={2}
        hint="Printed to the backend logs on first boot (SETUP_TOKEN). Required to provision the first admin."
      >
        <Input
          placeholder="paste the X-Setup-Token value from the backend logs"
          value={data.setup_token}
          onChange={(e) => update("setup_token", e.target.value)}
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
      {
        key,
        name: tpl.name,
        apiKey: "",
        defaultModel: tpl.models[0] ?? "",
        baseUrl: "",
      },
    ]);
  };

  const patchProvider = (key: string, patch: Partial<SelectedProvider>) => {
    update(
      "providers",
      selected.map((p) => (p.key === key ? { ...p, ...patch } : p)),
    );
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
              const keyless = KEYLESS_PROVIDERS.has(p.key);
              return (
                <div
                  key={p.key}
                  className="bg-surface-hi border border-hx rounded-[10px] p-3.5"
                >
                  <div className="flex items-center justify-between mb-2.5">
                    <div className="flex items-center gap-2">
                      <LLMIcon provider={tpl.key} size={22} className="rounded" />
                      <span className="text-[13px] font-semibold">{p.name}</span>
                      {p.providerId && <Chip tone="ok" dot>Saved</Chip>}
                    </div>
                    {keyless && <span className="text-[11px] text-ink-4">{tpl.note || "Auth via cloud SDK"}</span>}
                  </div>
                  <div className="grid gap-2" style={{ gridTemplateColumns: "1.4fr 1fr" }}>
                    <Input
                      type="password"
                      placeholder={keyless ? "n/a · cloud IAM / ADC" : "sk-…"}
                      disabled={keyless}
                      value={p.apiKey}
                      onChange={(e) => patchProvider(p.key, { apiKey: e.target.value })}
                    />
                    <Select
                      value={p.defaultModel}
                      options={tpl.models.length > 0 ? tpl.models : [p.defaultModel || ""]}
                      onChange={(e) => patchProvider(p.key, { defaultModel: e.target.value })}
                    />
                  </div>
                  {(p.key === "custom" || p.key === "local") && (
                    <div className="mt-2">
                      <Input
                        placeholder={p.key === "local" ? "http://localhost:11434" : "https://api.together.xyz/v1"}
                        value={p.baseUrl}
                        onChange={(e) => patchProvider(p.key, { baseUrl: e.target.value })}
                      />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      ) : (
        <div className="mt-5 px-4 py-3.5 bg-app border border-dashed border-hx-2 rounded-lg text-center text-[12px] text-ink-3">
          Pick one or more providers above. We recommend{" "}
          <strong className="text-ink-2">Anthropic</strong> for planning agents and{" "}
          <strong className="text-ink-2">DeepSeek</strong> for the code agent.
        </div>
      )}
    </div>
  );
}

function StepAgents({
  data,
  update,
}: {
  data: WizardData;
  update: <K extends keyof WizardData>(field: K, value: WizardData[K]) => void;
}) {
  const providers = data.providers;
  // Build a (providerKey/model) option list for the Select dropdowns.
  const optionsForProvider = (providerKey: string): string[] => {
    const tpl = LLM_PROVIDERS.find((p) => p.key === providerKey);
    return tpl ? tpl.models : [];
  };

  const patchRow = (agentKey: string, patch: Partial<AgentRouting>) => {
    update(
      "agents",
      data.agents.map((row) => (row.agentKey === agentKey ? { ...row, ...patch } : row)),
    );
  };

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
              {["Agent", "Role", "Provider", "Model", "Temperature", "Max tokens"].map((h) => (
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
            {BMAD_AGENTS.map((a, i) => {
              const row = data.agents.find((r) => r.agentKey === a.key);
              const providerKey = row?.providerKey ?? "";
              const modelOptions = optionsForProvider(providerKey);
              return (
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
                  <td className="px-3.5 py-2.5 w-[160px]">
                    {providers.length === 0 || !row ? (
                      <span className="font-mono text-[11px] text-ink-5">
                        configure a provider first
                      </span>
                    ) : (
                      <Select
                        value={row.providerKey}
                        options={providers.map((p) => ({ value: p.key, label: p.name }))}
                        onChange={(e) => {
                          const nextKey = e.target.value;
                          const nextModels = optionsForProvider(nextKey);
                          patchRow(a.key, {
                            providerKey: nextKey,
                            model: nextModels[0] ?? row.model,
                          });
                        }}
                        className="h-[30px]"
                      />
                    )}
                  </td>
                  <td className="px-3.5 py-2.5 w-[200px]">
                    {row && modelOptions.length > 0 ? (
                      <Select
                        value={row.model}
                        options={modelOptions}
                        onChange={(e) => patchRow(a.key, { model: e.target.value })}
                        className="h-[30px]"
                      />
                    ) : row ? (
                      <Input
                        value={row.model}
                        onChange={(e) => patchRow(a.key, { model: e.target.value })}
                        className="h-[30px]"
                      />
                    ) : (
                      <span className="font-mono text-[11px] text-ink-5">—</span>
                    )}
                  </td>
                  <td className="px-3.5 py-2.5 w-[100px]">
                    <Input
                      type="number"
                      step="0.1"
                      value={row?.temperature ?? 0.2}
                      onChange={(e) =>
                        patchRow(a.key, { temperature: Number(e.target.value) || 0 })
                      }
                      className="h-[30px]"
                    />
                  </td>
                  <td className="px-3.5 py-2.5 w-[110px]">
                    <Input
                      type="number"
                      value={row?.maxTokens ?? 4096}
                      onChange={(e) =>
                        patchRow(a.key, { maxTokens: Number(e.target.value) || 0 })
                      }
                      className="h-[30px]"
                    />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="mt-3.5 p-3 bg-app border border-hx rounded-lg flex gap-2 items-start">
        <Info className="h-3 w-3 text-ink-4 mt-0.5 shrink-0" />
        <div className="text-[11.5px] text-ink-3 leading-relaxed">
          Routing is hot-swappable mid-workflow. If a model rate-limits, Helix
          falls back to the next-cheapest model from the same provider, then across
          providers. The audit log captures every routing decision.
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
  const c = data.connection;
  const patch = (p: Partial<ConnectionDraft>) => update("connection", { ...c, ...p });

  return (
    <div className="max-w-[620px]">
      <p className="text-[12.5px] text-ink-3 mb-4">
        Add one source you want to migrate from. You can add more sources and
        targets later from <span className="font-mono text-ink">/connectors</span>.
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
        <FormRow label="Connector type" span={2}>
          <Select
            value={c.type}
            onChange={(e) => patch({ type: e.target.value })}
            options={CONNECTOR_OPTIONS}
          />
        </FormRow>
        <FormRow
          label="Connection name"
          span={2}
          hint="Used in the connector list and project source dropdown. Leave blank to skip."
        >
          <Input
            placeholder="Acme Production Postgres"
            value={c.name}
            onChange={(e) => patch({ name: e.target.value })}
          />
        </FormRow>
        <FormRow label="Host">
          <Input
            placeholder="db.acme.com"
            value={c.host}
            onChange={(e) => patch({ host: e.target.value })}
          />
        </FormRow>
        <FormRow label="Port">
          <Input
            type="number"
            value={c.port}
            onChange={(e) => patch({ port: e.target.value })}
          />
        </FormRow>
        <FormRow label="Database">
          <Input
            placeholder="warehouse"
            value={c.database}
            onChange={(e) => patch({ database: e.target.value })}
          />
        </FormRow>
        <FormRow label="SSL">
          <Select
            value={c.ssl}
            onChange={(e) => patch({ ssl: e.target.value })}
            options={["require", "verify-ca", "disable"]}
          />
        </FormRow>
        <FormRow label="Username">
          <Input
            placeholder="helix_reader"
            value={c.username}
            onChange={(e) => patch({ username: e.target.value })}
          />
        </FormRow>
        <FormRow label="Password">
          <Input
            type="password"
            placeholder="••••••••"
            value={c.password}
            onChange={(e) => patch({ password: e.target.value })}
          />
        </FormRow>
      </div>
      <div className="mt-3.5 flex gap-2">
        <Button variant="ghost" onClick={() => update("connection", { ...emptyConnection })}>
          <Play className="h-3 w-3" /> Reset fields
        </Button>
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
  const p = data.project;
  const patch = (next: Partial<ProjectDraft>) => update("project", { ...p, ...next });

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
            value={p.name}
            onChange={(e) => patch({ name: e.target.value })}
            required
          />
        </FormRow>
        <FormRow label="Source" hint="From the connection above.">
          <Input
            value={data.connection.name || "—  add a connection in step 3 to attach"}
            disabled
          />
        </FormRow>
        <FormRow label="Target">
          <Select
            value={p.target}
            onChange={(e) => patch({ target: e.target.value })}
            options={TARGET_OPTIONS}
          />
        </FormRow>
        <FormRow label="Owner">
          <Input value={`You · ${data.name || "First admin"}`} disabled />
        </FormRow>
        <FormRow label="Environment">
          <Select
            value={p.environment}
            onChange={(e) => patch({ environment: e.target.value })}
            options={["development", "staging", "production"]}
          />
        </FormRow>
        <FormRow
          label="Requirement brief"
          span={2}
          hint="The BMAD analyst (Mary) will expand this into a full product brief."
        >
          <textarea
            rows={4}
            placeholder="Migrate the GL_LEDGER, GL_TRANS, GL_RECON tables from Oracle production to Snowflake. Preserve audit columns. Run nightly delta until cutover."
            value={p.brief}
            onChange={(e) => patch({ brief: e.target.value })}
            className="w-full px-3 py-2.5 bg-surface border border-hx-2 rounded-md text-[12.5px] font-mono text-ink resize-y focus-ring"
          />
        </FormRow>
      </div>
    </div>
  );
}

function StepLaunch({ data, persisted }: { data: WizardData; persisted: PersistedIds }) {
  const providerCount = Object.keys(persisted.providerIds).length;
  const items: { label: string; value: string; mono?: boolean }[] = [
    { label: "Workspace",     value: data.organization_name || "—" },
    { label: "Slug",          value: data.organization_slug || "—", mono: true },
    { label: "Region",        value: data.region, mono: true },
    {
      label: "LLM providers",
      value:
        providerCount > 0
          ? `${providerCount} saved · ${data.providers.map((p) => p.name).join(", ")}`
          : "Configure later",
      mono: true,
    },
    {
      label: "Agent routing",
      value: persisted.mappingsSaved ? `6 agents · saved` : "Configure later",
      mono: true,
    },
    {
      label: "Source connection",
      value: persisted.sourceConnectionId
        ? data.connection.name
        : data.connection.name
          ? `${data.connection.name} (pending)`
          : "Configure later",
    },
    {
      label: "First project",
      value: persisted.projectId
        ? `${data.project.name}`
        : data.project.name || "Configure later",
    },
    {
      label: "Project ID",
      value: persisted.projectId || "—",
      mono: true,
    },
    { label: "Owner",         value: data.email || data.name || "—", mono: true },
  ];

  return (
    <div className="max-w-[680px]">
      <div className="flex items-center gap-3 px-4 py-3.5 bg-[var(--con-ok-soft)] border border-[#86EFAC] rounded-[10px] mb-5">
        <Check className="h-4 w-4 text-ok shrink-0" />
        <div>
          <div className="text-[14px] font-semibold text-ok">Workspace provisioned</div>
          <div className="text-[11.5px] text-ink-3 mt-0.5">
            Your org, providers, agent routing, and first project are saved. Open
            the console to start the BMAD planning chain.
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
          <li>Review or rotate LLM credentials in <span className="font-mono text-ink">/admin/llm-settings</span></li>
          <li>Tune agent-to-model mappings in <span className="font-mono text-ink">/admin/agent-mapping</span></li>
          <li>Add more source / target connectors at <span className="font-mono text-ink">/connectors</span></li>
          <li>Open your first project in <span className="font-mono text-ink">/projects</span></li>
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

/**
 * FormRow — label + field wrapper.
 *
 * Automatically generates a stable id via useId() and injects it into the
 * first React element child so that `<label htmlFor>` is always wired even
 * when the caller doesn't pass an explicit id.  Pass `htmlFor` to override
 * (e.g. when children is a complex fragment).
 */
function FormRow({
  label,
  hint,
  children,
  span,
  htmlFor: htmlForProp,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
  span?: 1 | 2;
  htmlFor?: string;
}) {
  const autoId = useId();
  const fieldId = htmlForProp ?? autoId;

  // Inject `id` into the first element child so the label binds correctly.
  const child = React.Children.toArray(children)[0];
  const enhancedChildren =
    child && React.isValidElement<{ id?: string }>(child)
      ? [React.cloneElement(child, { id: child.props.id ?? fieldId }), ...React.Children.toArray(children).slice(1)]
      : children;

  return (
    <div className={span === 2 ? "sm:col-span-2" : undefined}>
      <label htmlFor={fieldId} className="block text-[11.5px] font-medium text-ink-2 mb-1.5">
        {label}
      </label>
      {enhancedChildren}
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
        "w-full h-9 px-3 bg-surface border border-hx-2 rounded-md text-[12.5px] text-ink focus-ring disabled:bg-app-2 disabled:text-ink-4 " +
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
        "w-full h-9 px-2.5 bg-surface border border-hx-2 rounded-md text-[12.5px] text-ink focus-ring " +
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
