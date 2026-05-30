/**
 * Central marketing-site content for the Helix landing + layout components.
 *
 * Helix is an open-source, self-hosted, AI-powered database migration,
 * validation, reconciliation, and governance platform. Six BMAD agent
 * personas drive a 13-step, Temporal-orchestrated pipeline.
 *
 * Every exported symbol here is imported by a component under
 * `components/landing/*`, `components/layout/*`, or `pages/*`. Shapes are
 * matched exactly to how each consumer accesses the data — do not rename
 * fields without updating the consumers.
 */

// ---------------------------------------------------------------------------
// Site-level identity
// ---------------------------------------------------------------------------

export interface SiteInfo {
  name: string;
  tagline: string;
  oneLiner: string;
  github: string;
  license: string;
  domain: string;
  /** owner/repo slug rendered as `github.com/{repoSlug}`. */
  repoSlug: string;
}

export const SITE: SiteInfo = {
  name: "Helix",
  tagline: "Open-source AI migration platform",
  oneLiner:
    "Helix plans, validates, and reconciles enterprise database migrations with six BMAD agents and a 13-step pipeline — self-hosted, multi-LLM, and fully auditable. No SaaS, no telemetry, no lock-in.",
  github: "https://github.com/datainteg/helix-ai-migration",
  license: "Apache 2.0",
  domain: "helix.dev",
  repoSlug: "datainteg/helix-ai-migration",
};

// ---------------------------------------------------------------------------
// Navigation + footer
// ---------------------------------------------------------------------------

export interface NavItem {
  label: string;
  href: string;
}

export const NAV: NavItem[] = [
  { label: "Features", href: "/features" },
  { label: "Docs", href: "/docs" },
  { label: "Open source", href: "/open-source" },
  { label: "Roadmap", href: "/#roadmap" },
];

export interface FooterLink {
  label: string;
  href: string;
  external?: boolean;
}

export interface FooterColumns {
  product: FooterLink[];
  developers: FooterLink[];
  community: FooterLink[];
}

export const FOOTER: FooterColumns = {
  product: [
    { label: "Features", href: "/features" },
    { label: "Architecture", href: "/features" },
    { label: "Connectors", href: "/features" },
    { label: "Roadmap", href: "/#roadmap" },
  ],
  developers: [
    { label: "Documentation", href: "/docs" },
    { label: "Installation", href: "/docs/installation" },
    { label: "API reference", href: "/docs/api-reference" },
    {
      label: "GitHub",
      href: "https://github.com/datainteg/helix-ai-migration",
      external: true,
    },
  ],
  community: [
    { label: "Open source", href: "/open-source" },
    {
      label: "Contributing",
      href: "https://github.com/datainteg/helix-ai-migration/blob/main/CONTRIBUTING.md",
      external: true,
    },
    {
      label: "Issues",
      href: "https://github.com/datainteg/helix-ai-migration/issues",
      external: true,
    },
    {
      label: "Discussions",
      href: "https://github.com/datainteg/helix-ai-migration/discussions",
      external: true,
    },
  ],
};

// ---------------------------------------------------------------------------
// Hero CTAs + demo
// ---------------------------------------------------------------------------

export interface Cta {
  label: string;
  href: string;
}

export interface HeroCtas {
  primary: Cta;
  secondary: Cta;
  tertiary: Cta;
}

/** URL of the static HTML console mock, opened in a new tab. */
export const STATIC_DEMO_URL = "/";

export const HERO_CTAS: HeroCtas = {
  primary: { label: "View live demo", href: STATIC_DEMO_URL },
  secondary: { label: "Read the docs", href: "/docs" },
  tertiary: { label: "Star on GitHub", href: SITE.github },
};

// ---------------------------------------------------------------------------
// Problem / solution narrative
// ---------------------------------------------------------------------------

export interface NarrativeBlock {
  title: string;
  body: string[];
}

export const PROBLEM_BLOCK: NarrativeBlock = {
  title: "Migrations fail in the gaps between tools, teams, and tribal knowledge.",
  body: [
    "A real enterprise migration touches a dozen systems, a hundred tables, and years of undocumented business logic. The plan lives in someone's head, the mapping lives in a spreadsheet, and the validation never happens until production breaks.",
    "Off-the-shelf ETL moves bytes but can't reason about intent. Hand-written scripts don't reconcile, don't audit, and don't survive a schema change. When something drifts, nobody can prove what moved or why.",
  ],
};

export const SOLUTION_BLOCK: NarrativeBlock = {
  title: "One self-hosted stack that reasons, validates, and proves every step.",
  body: [
    "Helix puts six specialized AI agents on the job — analyst, PM, UX, architect, engineer, and tech-writer — each producing real, reviewable artifacts that the next agent reads as context.",
    "Every node in the 13-step pipeline writes markdown you can read, approve, and version. Row-level reconciliation and validation rules run on your data plane, and the full audit trail stays inside your infrastructure.",
  ],
};

// ---------------------------------------------------------------------------
// Features
// ---------------------------------------------------------------------------

export interface Feature {
  /** Key into the consumer's ICON_MAP (lucide icon name). */
  icon: string;
  title: string;
  desc: string;
}

export const FEATURES: Feature[] = [
  {
    icon: "Sparkles",
    title: "AI migration planning",
    desc: "Point Helix at a source and target. The agent pipeline drafts a phased migration plan, risk register, and cutover sequence you can edit and approve.",
  },
  {
    icon: "GitCompareArrows",
    title: "Schema & type mapping",
    desc: "Automatic column-to-column mapping with type coercion, nullability, and precision handling across heterogeneous engines — every decision is explainable.",
  },
  {
    icon: "ShieldCheck",
    title: "Row-level reconciliation",
    desc: "Hash-based and value-level reconciliation across source and target, with drift detection and diff reports down to the individual record.",
  },
  {
    icon: "ShieldAlert",
    title: "Validation rules",
    desc: "Author declarative validation rules — referential integrity, business invariants, distribution checks — and gate cutover on a green run.",
  },
  {
    icon: "Cpu",
    title: "Multi-LLM, your keys",
    desc: "Route each agent to OpenAI, Anthropic, Bedrock, Vertex, Azure, or a local model. Ten providers supported, all behind one adapter layer.",
  },
  {
    icon: "Package",
    title: "Audit trail & governance",
    desc: "Every artifact, approval, and run is versioned and signed. Export a complete, tamper-evident record of what moved, when, and on whose sign-off.",
  },
];

// ---------------------------------------------------------------------------
// Architecture layers + end-to-end feature map
// ---------------------------------------------------------------------------

export interface FeatureLayer {
  name: string;
  /** Hex color used for accents and gradients. */
  color: string;
  items: string[];
}

export const FEATURE_LAYERS: FeatureLayer[] = [
  {
    name: "Operator UI",
    color: "#4F46E5",
    items: ["Next.js console", "Sprint board", "Approval gates", "Audit viewer"],
  },
  {
    name: "Developer API",
    color: "#06B6D4",
    items: ["FastAPI backend", "18 routers", "Python SDK", "CLI"],
  },
  {
    name: "Data plane",
    color: "#15803D",
    items: ["Connectors", "Reconciliation engine", "Validation runner", "Temporal worker"],
  },
  {
    name: "Governance",
    color: "#B45309",
    items: ["Audit trail", "RBAC", "Secrets vault", "Tenant isolation"],
  },
];

/** Linear left-to-right chain of pipeline capabilities. */
export const FEATURE_MAP_CHAIN: string[] = [
  "Requirement intake",
  "Source discovery",
  "Schema mapping",
  "Migration plan",
  "Validation rules",
  "Execution",
  "Reconciliation",
  "Report export",
];

// ---------------------------------------------------------------------------
// BMAD agents + 13-step pipeline
// ---------------------------------------------------------------------------

export interface Agent {
  name: string;
  role: string;
  skill: string;
}

export const AGENTS: Agent[] = [
  {
    name: "Mary",
    role: "Analyst",
    skill: "Profiles the source estate, mines business rules, and writes the requirements brief the rest of the pipeline reads.",
  },
  {
    name: "John",
    role: "PM",
    skill: "Turns the brief into a phased migration plan with scope, risk register, and approval gates.",
  },
  {
    name: "Sally",
    role: "UX",
    skill: "Designs the operator review surfaces — what humans see, approve, and override at each gate.",
  },
  {
    name: "Winston",
    role: "Architect",
    skill: "Produces the schema and type mapping, target topology, and reconciliation strategy.",
  },
  {
    name: "Amelia",
    role: "Engineer",
    skill: "Generates and runs the migration and validation jobs on the Temporal worker against your data plane.",
  },
  {
    name: "Paige",
    role: "Tech-writer",
    skill: "Compiles the audit narrative, runbook, and final reconciliation report for hand-off and compliance.",
  },
];

/** The 13-step Temporal-orchestrated agent pipeline. */
export const PIPELINE_NODES: string[] = [
  "Intake",
  "Profile",
  "Requirements",
  "Plan",
  "Risk review",
  "Map schema",
  "Map types",
  "Validation rules",
  "Dry run",
  "Execute",
  "Reconcile",
  "Audit",
  "Report",
];

// ---------------------------------------------------------------------------
// Connectors
// ---------------------------------------------------------------------------

export interface Connector {
  name: string;
  /** Single-letter glyph rendered in the connector tile. */
  letter: string;
  /** Hex background color for the tile glyph. */
  color: string;
  category: string;
}

export const CONNECTORS: Connector[] = [
  { name: "PostgreSQL", letter: "P", color: "#336791", category: "database" },
  { name: "MySQL", letter: "M", color: "#00758F", category: "database" },
  { name: "Oracle", letter: "O", color: "#C74634", category: "database" },
  { name: "SQL Server", letter: "S", color: "#CC2927", category: "database" },
  { name: "Snowflake", letter: "S", color: "#29B5E8", category: "warehouse" },
  { name: "BigQuery", letter: "B", color: "#4285F4", category: "warehouse" },
  { name: "Databricks", letter: "D", color: "#FF3621", category: "lakehouse" },
  { name: "Amazon S3", letter: "S", color: "#569A31", category: "object store" },
];

// ---------------------------------------------------------------------------
// Install command
// ---------------------------------------------------------------------------

export const DOCKER_INSTALL =
  "curl -fsSL https://raw.githubusercontent.com/datainteg/helix-ai-migration/main/setup.sh | sudo bash";

// ---------------------------------------------------------------------------
// Roadmap
// ---------------------------------------------------------------------------

export interface RoadmapColumn {
  quarter: string;
  items: string[];
}

export const ROADMAP: RoadmapColumn[] = [
  {
    quarter: "Now",
    items: [
      "13-step BMAD pipeline",
      "Row-level reconciliation",
      "10-provider LLM layer",
      "Operator console + audit trail",
    ],
  },
  {
    quarter: "Next",
    items: [
      "Incremental / CDC migrations",
      "Custom validation rule packs",
      "SSO + fine-grained RBAC",
    ],
  },
  {
    quarter: "Later",
    items: [
      "Visual mapping editor",
      "Lineage graph export",
      "Multi-region cutover orchestration",
    ],
  },
  {
    quarter: "Exploring",
    items: [
      "On-prem air-gapped LLMs",
      "Marketplace for connectors",
      "Auto-generated test data",
    ],
  },
];

// ---------------------------------------------------------------------------
// Open-source principles
// ---------------------------------------------------------------------------

export const CONTENT_RULES_DISCLOSURE: string[] = [
  "Your data never leaves your infrastructure. Every connector, reconciliation, and validation runs on your own data plane — Helix has no remote control plane and ships zero telemetry.",
  "Every AI decision is an artifact you can read, edit, and reject. Agents propose; humans approve at every gate. Nothing executes against your databases without a recorded sign-off.",
  "The audit trail is tamper-evident and exportable. You can prove exactly what moved, when, under which plan, and on whose approval — to your auditors and to yourself.",
  "Apache 2.0, forever. Use it commercially, fork it, and self-host it with no usage caps, seat limits, or phone-home checks of any kind.",
];
