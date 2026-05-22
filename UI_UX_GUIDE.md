# UI/UX Guide

## Project Identity

| Item | Value |
|---|---|
| Product | Helix Migration |
| Repository | helix-ai-migration |
| Website | helix.datainteg.io |
| Tagline | Open-source AI-powered migration and validation platform. |
| Frontend image | datainteg/helix-ai-migration-frontend |
| Backend image | datainteg/helix-ai-migration-backend |
| Worker image | datainteg/helix-ai-migration-worker |

Helix Migration should feel like an enterprise migration command center: clear, trustworthy, efficient, and useful for both business and engineering teams.

## Product Experience

Helix Migration serves two main user modes:

| Mode | Audience | Goal |
|---|---|---|
| Business Mode | Sponsors, PMs, client stakeholders | Progress, risks, approvals, reports |
| Engineering Mode | Architects, data engineers, QA, DevOps | Metadata, mappings, validations, logs, workflow traces |

The UI should make complex migration workflows understandable without hiding technical depth from engineers.

## Figma-First Approach

Create a full Figma design system before heavy frontend implementation.

Recommended Figma structure:

```text
01_Foundations
02_Design_System
03_Components
04_Landing_Page
05_Admin_Panel
06_Main_Dashboard
07_Project_Workspace
08_Agent_Workflow
09_Connector_Hub
10_Validation_Center
11_Recon_Report
12_Settings
13_Developer_Mode
```

## Core Screens

- Login
- First admin setup
- Organization setup
- Main dashboard
- Admin dashboard
- User management
- Role management
- LLM provider settings
- Agent model mapping
- Project creation
- Requirement intake
- Project workspace
- Agent workflow canvas
- Source/target connector setup
- Schema metadata viewer
- Validation center
- Recon report
- Report center
- Audit logs
- System health

## Dashboard

Dashboard should show:

- Active projects
- Migration phase
- Workflow status
- Risk score
- Validation status
- Recon status
- Pending approvals
- Recent agent outputs
- Recent audit events

## Project Workspace

Project workspace should be the primary working area.

Suggested sections:

- Overview
- Requirements
- Source and target systems
- Schema metadata
- Agent workflow
- Validation
- Reconciliation
- Reports
- Approvals
- Activity and audit

## Agent Workflow Canvas

Use React Flow for:

- Agent sequence
- Human approval gates
- Status per agent
- Retry/failure markers
- Output links
- Workflow trace

Node states:

- Not started
- Running
- Waiting for approval
- Needs input
- Failed
- Completed

## Connector Hub

Connector hub should support:

- Connector catalog
- Source and target setup
- Test connection
- Schema scan
- Last sync status
- Credential rotation
- Error details

Do not expose secrets after save.

## Validation Center

Validation center should show:

- Rule catalog
- Validation runs
- Pass/fail summary
- Failed checks
- Severity
- Owner
- Suggested fix
- Exportable report

## Recon Reports

Recon reports should show:

- Source and target comparison
- Row count summary
- Checksum status
- Mismatch count
- Severity
- AI mismatch explanation
- Downloadable report artifacts

## Admin Panel

Admin panel should include:

- Users
- Roles
- Organizations
- LLM providers
- Agent model mapping
- Prompt templates
- Connectors
- Audit logs
- Security settings
- System health

Admin pages must be role-protected.

## Design Principles

- Complex backend, simple frontend.
- Make current workflow state obvious.
- Show what changed, who changed it, and when.
- Keep business summaries readable.
- Keep engineering details inspectable.
- Prefer clear tables and timelines over decorative cards.
- Avoid hiding critical status in hover-only interactions.
- Make approval decisions explicit and auditable.

## Component Rules

- Use shadcn/ui as the base component system.
- Use tables for dense operational data.
- Use cards for repeated items or focused summaries, not page-level decoration.
- Use tabs for related project workspace sections.
- Use badges for status and severity.
- Use dialogs for focused create/edit flows.
- Use toasts for transient feedback.
- Use inline validation for forms.
- Use skeleton states during loading.

## Color and Spacing

- Use a restrained enterprise palette.
- Use status colors consistently:
  - Green: passed/completed
  - Amber: warning/waiting
  - Red: failed/critical
  - Blue: active/running
  - Gray: inactive/not started
- Keep spacing consistent and compact enough for operational dashboards.
- Avoid one-color-heavy themes.

## Accessibility

- Support keyboard navigation.
- Provide visible focus states.
- Maintain color contrast.
- Use semantic headings.
- Do not rely on color alone for status.
- Provide accessible labels for icon buttons.

## Responsive Design

- Desktop-first for enterprise workflows.
- Tablet support for review and approvals.
- Mobile support for dashboards, approvals, and status checks.
- Complex canvases can provide simplified mobile views.

## Client-Friendly and Developer-Friendly

Business users need readable summaries, approvals, and reports. Developers need schemas, logs, mappings, validation failures, and workflow traces. The UI should support both without turning every screen into an expert-only interface.

## Developer Execution UI

The Developer Execution Layer adds developer-focused screens:

- Developer Workspace
- Code Review Center
- ETL Migration Workspace
- Artifact Explorer
- Side-by-side Diff Viewer
- AI Review Panel
- Notebook Preview
- DAG / Workflow Analyzer
- Version History Drawer
- Approval Modal

Recommended layout:

| Area | Content |
|---|---|
| Left panel | Project files, uploaded artifacts, versions |
| Center panel | Source code, generated code, notebook preview, diff view |
| Right panel | AI analysis, suggestions, risks, assumptions, approval actions |
| Bottom panel | Logs, validation output, generated files, version history |

## Code Review Center UX

The Code Review Center should support upload, analysis, review comments, security and quality findings, dependency extraction, transformation logic extraction, side-by-side diff, approval or rejection, and export of generated draft code.

## ETL Migration Workspace UX

The ETL Migration Workspace should support legacy job inventory, ETL code analysis, DAG/workflow analysis, dependency graph, transformation extraction, code conversion, Databricks notebook preview, validation mapping, and migration readiness score.

## Developer UI Rules

- Treat generated code as draft until approved.
- Keep original and generated artifacts visually distinct.
- Always show assumptions and limitations next to generated output.
- Provide explicit approve, reject, and request changes actions.
- Show version history and content hash metadata for artifacts.
- Do not hide security findings behind collapsed panels.

## Enterprise UI Additions

Design direction: premium, enterprise-grade, light theme first, dark theme later, client-friendly, developer-friendly, and modern SaaS quality comparable to Databricks, Linear, Airbyte, Vercel, Cursor, GitHub, and Temporal UI.

### Admin / Management UI

- Admin dashboard
- LLM settings
- User management
- Role management
- System health
- Audit logs
- Templates
- Plugin settings
- Notification settings
- Import/export center

Notification settings should include an Admin SMTP setup screen with SMTP host, port, username, masked password/secret reference, from email, TLS/STARTTLS options, enabled status, and test email action.

### Observability UI

- System Health page
- Worker status
- Agent execution logs
- Temporal workflow status
- Token usage dashboard
- LLM latency metrics

### Governance UI

- Audit trail
- Approval history
- Agent decision history
- Prompt execution history
- Artifact history

### Template UI

- Template library
- Template preview
- Use template action
- Create custom template

### Plugin UI

- Installed plugins
- Available plugin types
- Connector plugin settings
- Validation plugin settings

### Import / Export UI

- Export project
- Export report
- Export templates
- Import project configuration
