# Helix Migration — Install Snippet (Operators)

Canonical repo: <https://github.com/datainteg/helix-ai-migration>

`setup.sh` works on a fresh Ubuntu 24.04 LTS GCE VM with **nothing**
pre-installed. It auto-installs Docker Engine + Compose v2 via the
official `get.docker.com` script.

## One-command install (fresh Ubuntu 24 LTS GCP VM)

```bash
# Non-interactive curl|bash — pipes setup.sh into bash with sudo.
curl -fsSL https://raw.githubusercontent.com/datainteg/helix-ai-migration/main/setup.sh \
  | sudo bash -s -- \
      --non-interactive \
      --domain helix.example.com \
      --admin-email ops@example.com \
      --admin-password "$(openssl rand -base64 24)"
```

If you'd rather clone first (recommended — gives you a checkout to
inspect and re-run):

```bash
git clone https://github.com/datainteg/helix-ai-migration /opt/helix
cd /opt/helix
sudo ./setup.sh --non-interactive --domain helix.example.com
```

## Flags

| Flag | Purpose |
|---|---|
| `--non-interactive` / `--yes` | Never prompt; accept defaults. Required for `curl|bash`. |
| `--install-docker` | Force Docker bootstrap (default: auto-detect missing). |
| `--skip-docker-install` | Operator manages Docker out-of-band. |
| `--domain <host>` | Public hostname for TLS deploys (sets `HELIX_PUBLIC_DOMAIN`, builds frontend with `https://<host>` API base). |
| `--admin-email <addr>` | Pre-seed first-admin email (paired with `--admin-password`). |
| `--admin-password <pw>` | Pre-seed first-admin password. Written to `.helix/first-admin.json` (mode 600) for the wave-3 `helix admin bootstrap` CLI to consume. |
| `--rebuild` | `docker compose build --no-cache --pull`. |
| `--rotate-secrets --force --confirm-data-loss` | Rotate JWT/Encryption/Audit keys. **Destructive** — invalidates every encrypted LLM key + connector cred. |
| `--down` | Stop the stack (keeps data volumes). |
| `--nuke` | Stop + remove containers AND volumes. |

## Distro support (auto Docker install)

| Distro | Installer used |
|---|---|
| Ubuntu / Debian / Mint / Pop!_OS | `curl -fsSL https://get.docker.com \| sh` |
| Fedora / RHEL / CentOS / Rocky / Alma / Oracle Linux | `curl -fsSL https://get.docker.com \| sh` |
| Alpine | `apk add docker docker-cli-compose` |
| Arch / Manjaro / EndeavourOS | `pacman -Sy --noconfirm docker docker-compose` |
| Anything else | Manual: <https://docs.docker.com/engine/install/> then `--skip-docker-install`. |

## Cloud-metadata IP detection

If `--domain` is omitted, `setup.sh` probes GCE metadata first then
AWS IMDS (v2 + v1) and writes that public IP into
`NEXT_PUBLIC_API_URL=http://<IP>:8000` so the frontend bundle can reach
the backend from your browser. Falls back to `localhost` when no
metadata server is reachable.

## Ubuntu 24 LTS gotcha — iptables

If the VM was upgraded in place from 22.04, `iptables` may still point
at the legacy backend. `setup.sh` detects this and (with confirmation —
or automatically under `--non-interactive`) switches to
`iptables-nft` via `update-alternatives`. Without this, Docker's
bridge networking silently breaks readiness probes.

## Windows (PowerShell)

```powershell
.\setup.ps1 -NonInteractive `
            -Domain helix.example.com `
            -AdminEmail ops@example.com `
            -AdminPassword "$(([guid]::NewGuid().ToString()))"
```

Same flag semantics as the Linux script (PascalCase instead of
kebab-case). Docker Desktop must be installed manually; the script does
not auto-install on Windows.

## Verifying the install

```bash
# Backend health.
curl -fsSL https://helix.example.com/api/v1/readyz

# Containers.
docker compose -f docker-compose.yml -f docker-compose.build.yml ps

# First-admin wizard (or it was pre-seeded via --admin-email).
open https://helix.example.com/setup/first-admin
```
