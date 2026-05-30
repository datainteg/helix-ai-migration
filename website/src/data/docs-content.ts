/**
 * Documentation content for the Helix docs site.
 *
 * Consumed by `pages/DocsPage.tsx` and `components/docs/*`. The shapes here
 * are matched exactly to how those components access the data:
 *   - `DocEntry`  : indexed by `id`, rendered via `title`, `category`,
 *                   `summary`, `sections`, and optional `relatedFeatures`.
 *   - `DocSection`: `heading` + `content`, optional `bulletPoints` and
 *                   `codeBlock.code`.
 *   - `DOC_CATEGORIES`: ordered category labels matched against
 *                   `DocEntry.category` for sidebar grouping.
 *   - `findDoc(id)`: returns the matching `DocEntry` or `undefined`.
 */

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface DocCodeBlock {
  code: string;
}

export interface DocSection {
  heading: string;
  content: string;
  bulletPoints?: string[];
  codeBlock?: DocCodeBlock;
}

export interface DocEntry {
  /** URL slug, used as `/docs/{id}`. */
  id: string;
  title: string;
  /** Must be one of DOC_CATEGORIES for sidebar grouping. */
  category: string;
  summary: string;
  sections: DocSection[];
  /** Cross-links rendered as related-topic chips. */
  relatedFeatures?: string[];
}

// ---------------------------------------------------------------------------
// Categories (ordered for the sidebar)
// ---------------------------------------------------------------------------

export const DOC_CATEGORIES: string[] = [
  "Getting started",
  "Concepts",
  "Guides",
  "Reference",
];

// ---------------------------------------------------------------------------
// Docs
// ---------------------------------------------------------------------------

export const DOCS: DocEntry[] = [
  {
    id: "introduction",
    title: "Introduction",
    category: "Getting started",
    summary:
      "What Helix is, who it's for, and how the agent pipeline turns a migration plan into a verified, audited result.",
    sections: [
      {
        heading: "What is Helix?",
        content:
          "Helix is an open-source, self-hosted platform that plans, executes, validates, and reconciles enterprise database migrations using a pipeline of six specialized AI agents. It runs entirely on your own infrastructure — there is no managed control plane and no telemetry.",
      },
      {
        heading: "Who it's for",
        content:
          "Data engineering and platform teams responsible for moving production data between databases, warehouses, and lakehouses without losing fidelity, governance, or their audit trail.",
        bulletPoints: [
          "Platform teams consolidating legacy databases.",
          "Data engineers migrating to a cloud warehouse or lakehouse.",
          "Compliance owners who need a provable record of every change.",
        ],
      },
    ],
    relatedFeatures: ["Architecture", "BMAD agents", "Installation"],
  },
  {
    id: "installation",
    title: "Installation",
    category: "Getting started",
    summary:
      "Stand up the full Helix stack — backend, worker, postgres, redis, temporal, and the operator UI — on a single host in about five minutes.",
    sections: [
      {
        heading: "One-line install",
        content:
          "The setup script clones the repo, writes a starter .env, and brings up the docker-compose stack. Run it on a host with Docker and Docker Compose installed.",
        codeBlock: {
          code: "curl -fsSL https://raw.githubusercontent.com/datainteg/helix-ai-migration/main/setup.sh | sudo bash",
        },
      },
      {
        heading: "Verify the stack",
        content:
          "Once the containers are healthy, the operator console is available locally and the first-admin bootstrap flow lets you create your account.",
        bulletPoints: [
          "Backend API and worker report healthy in `docker compose ps`.",
          "Temporal UI is reachable for inspecting pipeline runs.",
          "Open the operator console and complete first-admin signup.",
        ],
      },
      {
        heading: "Requirements",
        content: "Helix is intentionally light on its install footprint.",
        bulletPoints: [
          "Linux host with Docker Engine 24+ and Docker Compose v2.",
          "At least 4 vCPU and 8 GB RAM for a comfortable single-node run.",
          "API key(s) for at least one supported LLM provider.",
        ],
      },
    ],
    relatedFeatures: ["Configuration", "Connectors", "Introduction"],
  },
  {
    id: "architecture",
    title: "Architecture",
    category: "Concepts",
    summary:
      "The four runtime layers — operator UI, developer API, data plane, and governance — and how they wire together through one API.",
    sections: [
      {
        heading: "Four layers",
        content:
          "Helix is organized into four clear boundaries. Each is independently deployable and talks to the others over the backend API.",
        bulletPoints: [
          "Operator UI — the Next.js console for review and approval.",
          "Developer API — FastAPI backend with 18 routers and a Python SDK.",
          "Data plane — connectors, reconciliation, validation, and the Temporal worker.",
          "Governance — audit trail, RBAC, secrets vault, and tenant isolation.",
        ],
      },
      {
        heading: "Orchestration",
        content:
          "Long-running migration and validation jobs run as Temporal workflows. This gives Helix durable execution, automatic retries, and a full history of every pipeline run.",
      },
    ],
    relatedFeatures: ["BMAD agents", "Reconciliation", "Introduction"],
  },
  {
    id: "bmad-agents",
    title: "BMAD agents",
    category: "Concepts",
    summary:
      "Six personas — Mary, John, Sally, Winston, Amelia, and Paige — each owning one stage of the 13-step pipeline and writing artifacts the next agent reads.",
    sections: [
      {
        heading: "The personas",
        content:
          "BMAD splits the work of a migration across six role-specialized agents. Each produces a real markdown artifact rather than an opaque result, so every decision is reviewable.",
        bulletPoints: [
          "Mary (Analyst) — profiles the source and writes the requirements brief.",
          "John (PM) — drafts the phased plan, scope, and risk register.",
          "Sally (UX) — designs the operator review and approval surfaces.",
          "Winston (Architect) — produces schema/type mapping and reconciliation strategy.",
          "Amelia (Engineer) — runs migration and validation jobs on the worker.",
          "Paige (Tech-writer) — compiles the audit narrative and final report.",
        ],
      },
      {
        heading: "Artifacts as context",
        content:
          "Each node writes a markdown artifact to the run. Downstream agents read upstream artifacts as context, and humans approve at the gates before execution proceeds.",
      },
    ],
    relatedFeatures: ["Architecture", "Reconciliation", "Introduction"],
  },
  {
    id: "connectors",
    title: "Connectors",
    category: "Guides",
    summary:
      "Connect to PostgreSQL, MySQL, Oracle, SQL Server, Snowflake, BigQuery, Databricks, and S3 out of the box — or add your own with a small Python adapter.",
    sections: [
      {
        heading: "Built-in sources",
        content:
          "Helix ships connectors for the most common enterprise databases, warehouses, lakehouses, and object stores. Configure a connector with credentials drawn from the secrets vault.",
        bulletPoints: [
          "Databases: PostgreSQL, MySQL, Oracle, SQL Server.",
          "Warehouses: Snowflake, BigQuery.",
          "Lakehouse: Databricks.",
          "Object store: Amazon S3.",
        ],
      },
      {
        heading: "Writing a custom connector",
        content:
          "Implement the adapter interface to add your own warehouse, legacy ETL endpoint, or SaaS source. The interface is intentionally small — most adapters take under a day.",
        codeBlock: {
          code: 'from helix.connectors import Connector\n\nclass MyConnector(Connector):\n    name = "my-source"\n\n    def list_tables(self): ...\n    def read_rows(self, table): ...\n    def write_rows(self, table, rows): ...',
        },
      },
    ],
    relatedFeatures: ["Installation", "Configuration", "Reconciliation"],
  },
  {
    id: "reconciliation",
    title: "Reconciliation & validation",
    category: "Guides",
    summary:
      "Run hash-based and value-level reconciliation between source and target, and gate cutover on a green validation run.",
    sections: [
      {
        heading: "How reconciliation works",
        content:
          "After a migration job runs, Helix compares source and target at the row level using configurable hashing and value checks, then produces a diff report down to the individual record.",
      },
      {
        heading: "Validation rules",
        content:
          "Author declarative rules that must pass before cutover. Rules can assert referential integrity, business invariants, row counts, and distribution checks.",
        bulletPoints: [
          "Referential integrity across migrated tables.",
          "Row-count and checksum parity between source and target.",
          "Business invariants expressed as SQL or rule expressions.",
        ],
      },
    ],
    relatedFeatures: ["BMAD agents", "Connectors", "API reference"],
  },
  {
    id: "configuration",
    title: "Configuration",
    category: "Reference",
    summary:
      "Environment variables and LLM provider settings that drive the stack — all .env-driven for self-hosted, open-source deployment.",
    sections: [
      {
        heading: "Core environment",
        content:
          "Network and service configuration is fully .env-driven so the same compose file works on a laptop or a production host.",
        codeBlock: {
          code: "# .env\nHELIX_PUBLIC_URL=http://localhost\nDATABASE_URL=postgresql://helix:helix@postgres:5432/helix\nTEMPORAL_HOST=temporal:7233\nLLM_PROVIDER=anthropic\nANTHROPIC_API_KEY=sk-...",
        },
      },
      {
        heading: "LLM providers",
        content:
          "Route each agent to a provider of your choice. Ten providers are supported behind a single adapter, including hosted gateways and local models.",
        bulletPoints: [
          "OpenAI, Anthropic, Google Vertex, Azure OpenAI.",
          "AWS Bedrock and other managed gateways.",
          "Local / self-hosted models for air-gapped deployments.",
        ],
      },
    ],
    relatedFeatures: ["Installation", "API reference", "Connectors"],
  },
  {
    id: "api-reference",
    title: "API reference",
    category: "Reference",
    summary:
      "The FastAPI backend exposes 18 routers covering connectors, plans, runs, reconciliation, and audit. Authenticate, then drive the pipeline over HTTP.",
    sections: [
      {
        heading: "Authentication",
        content:
          "All endpoints require an authenticated session or API token. Tokens are scoped per tenant and respected by RBAC.",
        codeBlock: {
          code: "curl -H \"Authorization: Bearer $HELIX_TOKEN\" \\\n  http://localhost/api/v1/runs",
        },
      },
      {
        heading: "Common endpoints",
        content: "The most-used routers when scripting against Helix.",
        bulletPoints: [
          "POST /api/v1/connectors — register a source or target.",
          "POST /api/v1/plans — kick off the agent pipeline.",
          "GET  /api/v1/runs/{id} — inspect a pipeline run and its artifacts.",
          "GET  /api/v1/runs/{id}/reconciliation — fetch the diff report.",
        ],
      },
    ],
    relatedFeatures: ["Configuration", "Reconciliation", "Architecture"],
  },
];

// ---------------------------------------------------------------------------
// Lookup
// ---------------------------------------------------------------------------

/** Return the doc whose `id` matches, or `undefined` if none does. */
export function findDoc(id: string): DocEntry | undefined {
  return DOCS.find((doc) => doc.id === id);
}
