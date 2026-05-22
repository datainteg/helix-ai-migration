# Frontend Guide

Helix Migration frontend should be a Next.js enterprise application for migration planning, validation, reconciliation, administration, and workflow tracking.

## Stack

- Next.js
- TypeScript
- Tailwind CSS
- shadcn/ui
- React Flow
- Framer Motion
- Zustand or similar client state when needed
- TanStack Query or similar server state when needed

## App Structure

Recommended structure:

```text
frontend/
  app/
    login/
    setup/
    dashboard/
    admin/
    projects/
  components/
  features/
    admin/
    projects/
    metadata/
    agent-workflow/
    connectors/
    validation/
    reconciliation/
    reports/
  lib/
    api/
    auth/
    utils/
  styles/
  public/
```

## Routing

Suggested routes:

```text
/login
/setup/first-admin
/dashboard
/admin/users
/admin/roles
/admin/llm-providers
/admin/agent-model-mapping
/admin/audit-logs
/projects
/projects/new
/projects/[projectId]
/projects/[projectId]/requirements
/projects/[projectId]/metadata
/projects/[projectId]/agent-workflow
/projects/[projectId]/validation
/projects/[projectId]/reconciliation
/projects/[projectId]/reports
/developer-workspace
/projects/[projectId]/artifacts
/projects/[projectId]/code-review
```

## Components

Use component boundaries that match product areas:

- Layout shell
- Sidebar navigation
- Top navigation
- Project switcher
- Status badge
- Risk badge
- Data table
- Empty state
- Confirm dialog
- Provider settings form
- Schema table viewer
- Agent workflow node
- Validation result table
- Recon summary panel
- CodeEditor
- DiffViewer
- ArtifactExplorer
- AIReviewPanel
- VersionHistoryDrawer
- NotebookPreview

## shadcn/ui Usage

Use shadcn/ui for:

- Buttons
- Inputs
- Forms
- Dialogs
- Dropdowns
- Tables
- Tabs
- Badges
- Toasts
- Command palette

Keep styling consistent and avoid one-off component systems.

## React Flow Usage

Use React Flow for:

- Agent workflow canvas
- Approval gates
- Migration phase visualization
- Schema lineage later
- Validation flow later

Nodes should support:

- Agent name
- Status
- Last updated time
- Error state
- Output link
- Approval action when relevant

## API Integration

- Use typed API clients.
- Centralize auth token handling.
- Centralize error handling.
- Never expose full API keys.
- Use loading, empty, and error states on every data surface.

## State Management

Use server state for backend data. Use client state only for local UI behavior:

- Active workspace panel
- Canvas selection
- Unsaved form state
- Filters
- View mode

## UI Design Rules

- Keep pages dense but readable.
- Use tables for operational data.
- Use badges for status.
- Use tabs for workspace sections.
- Use dialogs for focused edits.
- Do not hide destructive actions.
- Do not use decorative animation around critical information.
- Support business and engineering modes.

## Admin Pages

Admin pages should include:

- User management
- Role management
- Organization settings
- LLM provider settings
- Agent model mapping
- Connector management
- Prompt templates
- Audit logs
- System health

## Dashboard Pages

Dashboard should show:

- Active migrations
- Phase progress
- Open approvals
- Risk summary
- Validation status
- Recon status
- Recent activity

## Project Workspace Pages

Project workspace should include:

- Overview
- Requirements
- Source and target metadata
- Agent workflow
- Validation
- Reconciliation
- Reports
- Approvals
- Audit activity

## Developer Workspace Pages

Developer execution routes:

- `/developer-workspace`
- `/projects/[id]/artifacts`
- `/projects/[id]/code-review`

Developer components:

- `CodeEditor`
- `DiffViewer`
- `ArtifactExplorer`
- `AIReviewPanel`
- `VersionHistoryDrawer`
- `NotebookPreview`

Modern developer UI rules:

- Use a four-region layout: left artifact explorer, center code/diff/notebook view, right AI review panel, bottom logs and version history.
- Make generated code visibly draft until approved.
- Keep assumptions, limitations, security findings, and approval actions visible.
- Support side-by-side original vs generated review.
- Do not execute uploaded code in the browser.

## Final Route Map

- `/admin`
- `/admin/llm-settings`
- `/admin/users`
- `/admin/system-health`
- `/admin/audit-logs`
- `/dashboard`
- `/projects`
- `/projects/[id]`
- `/projects/[id]/agents`
- `/projects/[id]/validation`
- `/projects/[id]/recon`
- `/projects/[id]/artifacts`
- `/projects/[id]/code-review`
- `/projects/[id]/developer-workspace`
- `/templates`
- `/plugins`
- `/import-export`
- `/admin/notifications`
- `/admin/notifications/smtp`

## Enterprise Component Concepts

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
- `SmtpSettingsForm`
- `NotificationRulesTable`

## Testing and Performance

- Test route guards, RBAC-driven navigation, form validation, and empty/error/loading states.
- Use mocked API clients for component tests.
- Keep large tables virtualized when needed.
- Keep React Flow canvases bounded and lazy-load heavy developer workspace panels.
- Do not fetch full artifact contents until user opens the artifact or diff view.
