# Notification System

## Purpose

Notifications help teams respond to approvals, validation failures, agent completion, failed jobs, and system events.

## Planned Channels

- Email
- Slack
- Microsoft Teams
- Webhooks

## SMTP Configuration

SMTP should be configurable from the Admin panel under notification settings.

Admin SMTP fields:

- SMTP host
- SMTP port
- Username
- Password or secret reference
- From email
- From name
- TLS/STARTTLS toggle
- Enabled/disabled status
- Test email recipient

Security rules:

- SMTP passwords must be encrypted before storage or referenced from an external secret manager.
- SMTP passwords must never be displayed after save.
- UI should show only masked values.
- SMTP configuration changes and test-email sends should be audit logged.
- Organization-level separation must apply to notification settings.

MVP may store encrypted SMTP settings and support a test configuration endpoint, while full notification delivery rules can remain future scope.

## Planned Events

- Approval reminders
- Validation failure alerts
- Reconciliation failure alerts
- Agent completion alerts
- Failed job alerts
- Connector health alerts
- LLM provider failure alerts

## MVP Scope

MVP may define notification settings and tables but does not need full notification delivery.
