# Business Sign-off Workflow

After the recon report is approved, a sign-off email **draft** is created — never
auto-sent. The user reviews/edits and explicitly sends.

## Flow

1. `POST /projects/{id}/signoff/draft` builds a draft from the approved recon
   report:
   - subject: `Migration reconciliation sign-off required — <alias>`
   - body: project alias/name, source/target system, validation summary, recon
     executive summary, approval request, next steps
   - attachments **linked** (referenced in the body): the recon report PDF +
     validation summary. (The email transport sends HTML/text; the report is
     linked rather than binary-attached.)
2. `PATCH /signoff/{id}` edits recipient / subject / body (draft only).
3. `POST /signoff/{id}/send` sends via the org's configured email settings
   (SMTP/SendGrid). **SMTP secrets are never exposed** — they live in the
   email-settings service. If email is disabled/unconfigured the send logs and
   returns without error; the draft is still marked `sent` with `sent_at`.
4. `POST /signoff/{id}/mark-approved` / `/mark-rejected` records the business
   decision (`agent:approve`).

Statuses: `draft → sent → approved | rejected`. Every event is audited.

## UI

`…/signoff` — status, draft editor (recipient/subject/body), attachments, HTML
preview, Save & Send, mark approved/rejected, and an audit trail. Reachable from
the recon report "Send for sign-off" link and the Sign-off tab.

## Security

- Email is never auto-sent (draft → user review → send).
- SMTP/SendGrid secrets are not exposed by these endpoints.
- Sign-off events (`signoff_draft_created`, `signoff_sent`, `signoff_approved`,
  `signoff_rejected`) are written to the audit log.
