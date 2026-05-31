# Developer Workspace & code-server (optional)

Helix has a stage-gated **Developer Workspace**: Amelia (the dev agent) generates
migration code from the project's **approved** architecture/plan context, and that
code is stored as **draft** `generated_code_artifacts`, reviewed, and approved in
the Helix UI.

> **The Helix backend never executes generated code.** It is data until a human
> reviews and approves it. Execution (if any) happens only in an isolated,
> operator-provisioned workspace — never in the API process.

## Workspace types

`developer_workspaces.workspace_type`:

| type | meaning |
|------|---------|
| `artifact_only` (default) | No container. Code is generated, reviewed and approved entirely inside Helix. Safe everywhere. |
| `external` | The team uses their own IDE/repo; Helix only tracks metadata + artifacts. |
| `code_server` | An isolated browser IDE (VS Code) provisioned via the optional compose profile below. |

`POST /workspaces/{id}/start` for a `code_server` workspace only records the
expected container name + URL — it does **not** spawn Docker. Provisioning the
container is an explicit operator action (below) and is gated on
`HELIX_CODE_SERVER_ENABLED`.

## Enabling code-server (opt-in)

1. Set a strong password and enable the feature in `.env`:

   ```
   CODE_SERVER_PASSWORD=<long-random-secret>
   HELIX_CODE_SERVER_ENABLED=1
   HELIX_CODE_SERVER_BASE_URL=https://workspace.example.com   # optional, for URL display
   ```

2. Start only the code-server service (it is behind the `workspace` profile, so a
   normal `docker compose up` never starts it):

   ```
   docker compose --profile workspace up -d code-server
   ```

3. Open it locally at `http://127.0.0.1:8443` (password = `CODE_SERVER_PASSWORD`).

## Security limitations — read before exposing it

- **Isolation:** the container mounts **only** the dedicated `helix_workspace`
  Docker volume at `/home/coder/workspace`. It does **not** mount the host root,
  the Helix repo, or any database. Do not add such mounts.
- **No backend execution:** generated code is draft data in Postgres. The Helix
  API/worker never run it. Only the (separate) code-server container can run code,
  and only against its own volume.
- **Bound to localhost:** the service publishes `127.0.0.1:8443` only. Before
  exposing it to a network, put it behind the TLS reverse proxy (`tls` profile)
  **and** an authenticating layer; code-server's password auth alone is not
  sufficient for internet exposure.
- **Per-project folders:** use one subfolder per project alias
  (e.g. `HXM-482913-WS1/`) under the workspace volume; do not share secrets
  across projects.
- **Secrets:** never paste connector credentials into the workspace. Helix keeps
  connector secrets encrypted and never feeds them to agents or workspaces.
- **Resource cap:** the service is capped at 1 GB RAM; raise deliberately.

If you do not need a browser IDE, leave code-server disabled — the
`artifact_only` flow (generate → review → approve → download) covers the full
lifecycle without running any code.
