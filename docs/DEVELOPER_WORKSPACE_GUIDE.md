# Developer Workspace & Generated Code

Amelia (the dev agent) generates migration code from the project's **approved**
architecture/plan context. Generated code is **draft data** — reviewed and
approved in Helix and **never executed by the backend**.

## Generated code

`POST /projects/{id}/generated-code/generate` runs Amelia, splits fenced code
blocks into individual `generated_code_artifacts` rows (SQL, Python, notebooks,
DAGs, …), each `status=draft`. You can also create code manually
(`POST …/generated-code`).

Lifecycle: `draft → reviewed → approved` (or `rejected`).
- Mark reviewed → `project:write`.
- Approve → `agent:approve`.

UI: `…/developer-workspace/code` (workspaces bar + Generate Code + file list +
viewer + review/approve/download) and `…/developer-workspace/review` (review
queue). The existing workspace page (artifact explorer + diff) is unchanged.

## Workspaces

`developer_workspaces` track a per-project workspace:

| type | behaviour |
|------|-----------|
| `artifact_only` (default) | no container — generate/review/approve in Helix |
| `external` | team uses its own IDE; Helix tracks metadata only |
| `code_server` | optional isolated browser IDE (opt-in) |

`start`/`stop` manage state only — the backend never spawns Docker. For
`code_server`, start is gated on `HELIX_CODE_SERVER_ENABLED` and only records the
expected container name + URL.

## code-server (optional)

See **[WORKSPACE.md](../WORKSPACE.md)** for the opt-in `docker compose --profile
workspace` setup and its security limitations (isolated volume, localhost bind,
password auth, no host-root mount, no backend execution).
