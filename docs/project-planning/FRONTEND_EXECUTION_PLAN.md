# Frontend Execution Plan

## Stack

- Next.js
- TypeScript
- Tailwind CSS
- shadcn/ui
- React Flow
- Framer Motion

## MVP Routes

| Route | Purpose |
|---|---|
| `/login` | User login |
| `/setup/first-admin` | First admin setup |
| `/dashboard` | Management dashboard |
| `/admin` | Admin dashboard |
| `/admin/llm-settings` | LLM providers and model mapping |
| `/admin/users` | User management |
| `/admin/system-health` | Health and worker status |
| `/admin/audit-logs` | Audit log review |
| `/projects` | Project list |
| `/projects/[id]` | Project workspace |
| `/projects/[id]/agents` | Agent workflow canvas |
| `/projects/[id]/validation` | Validation center |
| `/projects/[id]/recon` | Reconciliation reports |
| `/projects/[id]/artifacts` | Artifact explorer |
| `/projects/[id]/code-review` | Code Review Center |
| `/projects/[id]/developer-workspace` | Developer workspace |
| `/templates` | Static template library |
| `/plugins` | Plugin placeholder and roadmap |
| `/import-export` | Import/export center |

## Layout Shells

- Public/auth shell
- Main app shell
- Admin shell
- Project workspace shell
- Developer workspace split-panel shell

## Reusable Components

- `DashboardCards`
- `AgentWorkflowCanvas`
- `ArtifactExplorer`
- `DiffViewer`
- `AIReviewPanel`
- `NotebookPreview`
- `VersionHistoryDrawer`
- `ApprovalModal`
- `SystemHealthPanel`
- `AuditLogTable`
- `TemplateLibrary`
- `PluginRegistry`

## MVP Pages

| Page | Minimum behavior |
|---|---|
| Dashboard | Project status, pending approvals, recent activity |
| Admin LLM Settings | Provider CRUD, masked keys, key rotation, model mapping |
| Projects | List and create projects |
| Project Detail | Requirement intake and workspace tabs |
| Agent Workflow | React Flow BMAD workflow states and outputs |
| Developer Workspace | Artifact explorer, diff area, AI panel, approval actions |
| Validation/Reconciliation | Basic report summaries |
| Audit Logs | Filterable security and workflow events |
| System Health | Component status and failed job summary |

## State Management

- Use TanStack Query for server state.
- Use local component state for forms and transient UI.
- Use Zustand only for cross-page workspace state when needed.
- Keep API response types explicit.

## Mock Data First Approach

Use fixture data for early frontend shells before backend APIs are complete. Replace fixtures with typed API clients as endpoints stabilize. Mock data must not become the source of truth for business rules.

## API Integration Approach

- Centralize API client setup.
- Handle auth token refresh consistently.
- Use typed request and response contracts.
- Show loading, empty, error, success, and permission states.
- Never display full API keys or secret values.

## UI Quality Rules

- Light theme first, dark theme later.
- Enterprise SaaS quality, dense but readable.
- Use tables for operational data.
- Use React Flow for workflows and lineage.
- Keep generated code clearly marked as draft.
- Show assumptions, limitations, risks, and approval status near generated artifacts.
- Do not hide security findings behind hover-only UI.

## Build Order

1. App shell and navigation
2. Auth pages
3. Admin pages
4. Dashboard and project list
5. Project workspace
6. Agent workflow canvas
7. Developer workspace shell
8. Diff viewer and artifact panels
9. Validation/recon pages
10. Audit and health pages
11. UI polish and screenshots

## Related Architecture Docs

| Doc | What it covers |
|---|---|
| `UI_UX_GUIDE.md` | Design principles, Figma plan, component rules, business/engineering modes |
| `docs/frontend/FRONTEND_GUIDE.md` | Routes, components, state management, API integration, UI quality rules |
| `docs/developer-workspace/DEVELOPER_WORKSPACE.md` | Workspace layout, artifact types, approval lifecycle |
| `docs/developer-workspace/CODE_REVIEW_CENTER.md` | Upload, analysis, diff viewer, comments, approvals |
| `docs/developer-workspace/ETL_MIGRATION_WORKSPACE.md` | ETL workflow, DAG analysis, notebook generation |
