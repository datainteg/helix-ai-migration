import type { StageStatus } from "@/lib/lifecycle/api";

// BMAD persona / agent code → human label.
const AGENT_LABELS: Record<string, string> = {
  project_context: "Project Context",
  "bmad-agent-analyst": "Mary · Business Analyst",
  "bmad-agent-architect": "Winston · System Architect",
  "bmad-agent-pm": "John · Product Manager",
  "bmad-agent-ux-designer": "Sally · UX Designer",
  "bmad-agent-dev": "Amelia · Senior Engineer",
  qa: "QA Agent",
  recon: "Recon Agent",
  "bmad-agent-tech-writer": "Paige · Technical Writer",
  __orchestration__: "Orchestration (system)",
  __human__: "Human sign-off",
  __system__: "System",
};

export function agentLabel(code: string | null | undefined): string {
  if (!code) return "—";
  return AGENT_LABELS[code] || code;
}

// Short objective shown on the stage detail page (mirrors backend STAGE_PRODUCE intent).
export const STAGE_OBJECTIVE: Record<string, string> = {
  PROJECT_CONTEXT: "Establish the migration objective, source/target systems, scope, assumptions, constraints, risks and the initial execution strategy.",
  BUSINESS_ANALYSIS: "Capture business requirements, use cases, stakeholders, acceptance criteria, data domains, risks and success metrics.",
  ARCHITECTURE: "Define the source→target and migration architecture, connector plan, schema-discovery, validation, recon, security/governance and deployment approach.",
  PROJECT_PLANNING: "Break the work into epics, stories, milestones, dependencies, timeline, resource assumptions and risks.",
  UX_DESIGN: "Design the user journeys, key screens, interaction notes and accessibility considerations (optional).",
  SPRINT_GENERATION: "Produce the sprint list, goals, tasks, owners, dependencies, validation/recon checkpoints and approval gates.",
  SPRINT_EXECUTION: "Orchestration stage — sprints are executed and tracked here.",
  DEVELOPMENT: "Generate the implementation plan, code/skeletons, testing instructions, assumptions and the files created.",
  VALIDATION: "Define test cases, expected validation evidence, the validation checklist and pass/fail criteria.",
  RECONCILIATION: "Define the recon strategy, checks, recon SQL/Python, report structure and business sign-off criteria.",
  SIGN_OFF: "Human sign-off of the migration before closure.",
  DOCUMENTATION: "Produce the runbook, technical documentation, business summary and closure checklist.",
  CLOSURE: "System closure — the project is finalised and archived.",
};

export function isAgentRunnable(code: string | null | undefined): boolean {
  if (!code) return false;
  return !["__orchestration__", "__human__", "__system__"].includes(code);
}

// Short "next required action" hint per stage status.
export function nextActionHint(status: StageStatus, agentRunnable: boolean): string {
  switch (status) {
    case "not_started": return agentRunnable ? "Run agent to generate the artifact" : "Awaiting upstream completion";
    case "running": return "Agent is running…";
    case "generated":
    case "under_review":
    case "resubmitted": return "Review, edit or approve the artifact";
    case "edit_requested": return "Address changes, then resubmit";
    case "rejected": return "Rejected — regenerate or resubmit";
    case "failed": return "Run failed — retry";
    case "approved":
    case "completed": return "Done — continue to the next stage";
    case "skipped": return "Skipped";
    default: return "";
  }
}
