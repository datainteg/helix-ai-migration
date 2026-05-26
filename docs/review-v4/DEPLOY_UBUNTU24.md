# Helix Migration — Ubuntu 24.04 LTS Deployment Compatibility Audit

**Audited:** 2026-05-26  
**Branch:** main  
**Files reviewed:** `setup.sh`, `docker-compose.yml`, `backend/Dockerfile`, `worker/Dockerfile`, `frontend/Dockerfile`, `DEPLOY.md`, `docs/deployment/INSTALLATION.md`, `backend/requirements.txt`, `backend/requirements.lock`, `worker/requirements.lock`, `backend/app/security/ssrf.py`, `scripts/restore.sh`

---

## Summary verdict

Ubuntu 24.04 LTS is a viable deployment target with no showstopper blockers. Two items require action before `./setup.sh` can be called reliably on a fresh Ubuntu 24 host: the Docker install method documented in `DEPLOY.md` and the DNS stub-resolver interaction with Docker. Everything else is either low-risk or already correctly handled.

---

## Finding 1 — iptables / nftables

**Severity: 🟠 Medium — action required before first run**

Ubuntu 24.04 defaults to nftables as the kernel firewall framework. Docker Engine 24+ ships with iptables-nft support compiled in and selects the correct backend automatically (`iptables -V` reports `nf_tables` on Ubuntu 24). The Docker bridge network and `docker compose up` work out of the box **as long as Docker is installed from the official Docker CE repository** (see Finding 5 below).

The risk arises if the operator installs the `docker.io` package from Ubuntu's universe repository (version 24.0.x as of 24.04 GA). That package predates the nftables-aware iptables shim and can leave the `DOCKER-USER` chain absent from nftables, silently breaking inter-container routing.

`setup.sh` currently only checks that the `docker` binary exists and that `docker compose version` succeeds. It does **not** verify the Docker source or iptables backend.

**Recommendation:** Add a preflight check in `setup.sh`:

```bash
# After the existing Docker version check, add:
if docker info 2>/dev/null | grep -q 'Storage Driver: overlay2'; then
  # Check iptables mode — warn if not nft on Ubuntu 24
  if [ -f /etc/os-release ]; then
    . /etc/os-release
    if [ "${VERSION_ID:-}" = "24.04" ] && iptables --version 2>/dev/null | grep -q 'legacy'; then
      warn "Ubuntu 24.04 detected with iptables-legacy. Docker networking may fail."
      warn "Run: sudo update-alternatives --set iptables /usr/sbin/iptables-nft"
      warn "     sudo update-alternatives --set ip6tables /usr/sbin/ip6tables-nft"
      warn "Then restart Docker: sudo systemctl restart docker"
    fi
  fi
fi
```

No changes to `docker-compose.yml` are needed.

---

## Finding 2 — cgroup v2 default

**Severity: 🟡 Low — no action required, document only**

Ubuntu 24.04 runs exclusively on cgroup v2 (unified hierarchy). The following were checked:

- **Temporal `temporalio/auto-setup:1.25.0`** — Java-based; the JVM is cgroup-v2 aware since JDK 15. This image bundles JDK 21. No issue.
- **asyncpg** — pure Python async Postgres driver; has no cgroup dependency.
- **Python 3.11 slim images** — base images are Debian Bookworm which ships with a cgroup-v2-aware kernel and systemd stub. No issue.
- **`deploy.resources.limits.memory`** in `docker-compose.yml** — memory limits enforce via cgroup v2 `memory.max`. Docker Compose v2 handles this transparently.

No `--cgroupns`, `cgroup_parent`, or `cgroupv1`-specific flags appear anywhere in the compose file or Dockerfiles.

**Verdict:** cgroup v2 is fully compatible with this stack as-is.

---

## Finding 3 — AppArmor

**Severity: 🔵 Informational**

Ubuntu 24.04 ships with AppArmor active and includes Docker's default `docker-default` profile. The profile is applied automatically to every container that does not specify `security_opt: apparmor:unconfined`.

None of the services in `docker-compose.yml` set a custom AppArmor profile or `security_opt`. All containers run under `docker-default`, which:

- Allows normal filesystem access, networking, and process management.
- Blocks raw socket creation, `ptrace` across containers, and `/proc` mounts.
- Is compatible with FastAPI/uvicorn, asyncpg, Redis clients, and the Temporal SDK.

The one area to watch: the worker's healthcheck uses `asyncio` + `temporalio.client.Client.connect`. This makes an outbound TCP connection to port 7233 — permitted under `docker-default`.

**Verdict:** No AppArmor issues expected. If a future connector requires a native binary with extended capabilities, add a targeted `security_opt` override in a compose override file rather than disabling AppArmor globally.

---

## Finding 4 — systemd / loginctl linger for non-root deploy

**Severity: 🟠 Medium — document required for production ops**

`DEPLOY.md` and `setup.sh` give no guidance on running as a non-root user. On Ubuntu 24.04, if the operator creates a dedicated `helix` system account (recommended) and adds it to the `docker` group, the following applies:

- User systemd units (`~/.config/systemd/user/helix.service`) are only started at login and stopped at logout unless linger is enabled.
- Without `loginctl enable-linger helix`, the Docker Compose stack dies when the SSH session exits, even with `restart: unless-stopped`.

**Recommendation:** Add to `DEPLOY.md` under "Production Deployment Notes":

```bash
# If running as a non-root user (recommended):
sudo loginctl enable-linger <deploy-user>

# Optional: manage the stack as a user systemd service
# Create ~/.config/systemd/user/helix.service pointing to:
#   ExecStart=/usr/bin/docker compose -f /opt/helix/docker-compose.yml ... up
#   ExecStop=/usr/bin/docker compose ... down
# Then: systemctl --user enable --now helix
```

The `restart: unless-stopped` policy in `docker-compose.yml` handles container-level crashes correctly once the initial `docker compose up -d` is issued under a lingering user or root.

---

## Finding 5 — Docker install path (docker.io vs Docker CE)

**Severity: 🔴 High — setup.sh actively guides users toward the wrong package**

`setup.sh` line 101 prints:

```
apt install docker-compose-plugin (Linux)
```

`DEPLOY.md` prerequisites table does not specify which Docker package to install. `docs/deployment/INSTALLATION.md` says only "Docker" and "Docker Compose" with no install instructions.

On Ubuntu 24.04, `apt install docker.io` installs Docker 24.0.x from Ubuntu's universe repository. This version:

- Ships an older iptables shim with reduced nftables compatibility (see Finding 1).
- Does not receive upstream Docker security patches promptly.
- Includes `docker-compose` v1 (the deprecated Python version) rather than the Compose v2 plugin — `setup.sh`'s `docker compose version` check would pass only if `docker-compose-plugin` is separately installed.

The correct install path for Ubuntu 24.04 is Docker's official APT repository:

```bash
# Remove conflicting packages
for pkg in docker.io docker-doc docker-compose docker-compose-v2 podman-docker containerd runc; do
  sudo apt-get remove -y $pkg 2>/dev/null || true
done

# Add Docker's official GPG key and repo
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io \
  docker-buildx-plugin docker-compose-plugin
```

**Recommendation:** Add an Ubuntu-specific "Install Docker" section to `DEPLOY.md` (or link to the official Docker docs for Ubuntu) and update the error message in `setup.sh` line 101 to reference the correct package.

---

## Finding 6 — Python 3.12 default on Ubuntu 24 host

**Severity: 🔵 Informational**

Ubuntu 24.04 ships Python 3.12 as the system Python (`/usr/bin/python3`). The project does not use the host Python at any point:

- All Python workloads run inside containers built from `python:3.11-slim`.
- `setup.sh` never invokes `python` or `pip` on the host.
- `scripts/generate-secrets.sh` uses `openssl rand` and `base64` — no Python.

**Verdict:** Host Python version is irrelevant. No action needed. Document in `DEPLOY.md` under Prerequisites that host Python is not required.

---

## Finding 7 — Node.js version on host

**Severity: 🟡 Low — relevant only for host-side development, not production deploy**

Ubuntu 24.04's APT repository ships Node.js 18.x (LTS as of Noble). The `frontend/Dockerfile` builds on `node:20-alpine`. The built Next.js standalone output (`server.js`) runs inside the container against Node 20.

If operators build the frontend directly on the host (outside Docker) — not the recommended path — they need Node 20+. Ubuntu 24 ships Node 18 via APT; operators would need NodeSource or `nvm` to get 20+.

`setup.sh` performs all builds inside Docker (`docker compose build`), so host Node is not used in the standard flow.

**Recommendation:** Add a note to `DEPLOY.md`: "If building outside Docker for local development, install Node.js 20+ via [NodeSource](https://nodesource.com/) or nvm. Ubuntu 24's default `apt install nodejs` provides Node 18."

---

## Finding 8 — glibc 2.39 binary wheel compatibility

**Severity: 🟡 Low — potential build-time concern, not runtime**

Ubuntu 24.04 ships glibc 2.39. However, all Python dependency installation occurs inside `python:3.11-slim` containers (Debian Bookworm, glibc 2.36). The compiled wheels are therefore built and run against Debian's glibc, not the Ubuntu host's glibc.

The packages most likely to ship binary wheels with glibc requirements were inspected in `backend/requirements.lock`:

| Package | Version in lock | Wheel type | glibc concern |
|---------|----------------|------------|---------------|
| `pyodbc` | 5.3.0 | `manylinux_2_17` | None — 2.17 threshold met by Bookworm's 2.36 |
| `grpcio` | 1.80.0 | `manylinux_2_17` | None |
| `cryptography` | 48.0.0 | `manylinux_2_28` | None — 2.28 met by Bookworm 2.36 |
| `reportlab` | 4.5.1 | Pure Python + freetype C ext | Builds from source inside container; no host glibc dependency |
| `psycopg2-binary` | >= 2.9.0 | `manylinux_2_17` | None |

**Note:** `requirements.lock` was generated with Python 3.13 (pip-compile header line 4) but the Dockerfiles install into Python 3.11. This version mismatch means the lock file's resolved package set may differ from what pip actually installs inside the 3.11 container. This is a pre-existing reproducibility issue, not Ubuntu 24-specific, but should be tracked.

**Verdict:** No glibc compatibility issues for Ubuntu 24.04. The lockfile-vs-Python-version mismatch is a separate concern.

---

## Finding 9 — PostgreSQL 16 client compatibility

**Severity: 🔵 Informational**

Ubuntu 24.04 ships `postgresql-client-16`. The compose stack uses `postgres:16.4` as the database image. Versions are aligned.

`scripts/restore.sh` uses `psql` via `docker compose exec -T postgres psql` — the client inside the `postgres:16.4` container, not the host client. Host `pg_dump`/`psql` is not invoked. No compatibility gap.

`DEPLOY.md`'s backup cron example (`docker compose exec -T postgres pg_dump`) similarly uses the containerized client. This is correct and avoids any host-version dependency.

**Verdict:** No action required. If operators ever use the host `pg_dump` directly (e.g., from a CI machine running Ubuntu 24), `postgresql-client-16` from APT is the correct version for the `postgres:16.4` server.

---

## Finding 10 — GCP metadata server SSRF guard

**Severity: 🔵 Informational — correctly handled**

`backend/app/security/ssrf.py` was reviewed. The `_FORBIDDEN_HOSTS` set explicitly includes:

```python
_FORBIDDEN_HOSTS = {
    "metadata.google.internal",
    "metadata",
    "169.254.169.254",     # GCE / AWS / Azure instance metadata
    "fd00:ec2::254",       # AWS IMDSv2 IPv6
}
```

Additionally, `_is_forbidden_ip` rejects any address that is loopback, link-local, private, multicast, unspecified, or reserved. The `169.254.169.254` link-local address would be caught by the `ip.is_link_local` check even without the explicit denylist entry.

The guard is applied at both admit-time (webhook create/update) and send-time (delivery), and DNS resolution is performed for every A/AAAA record to prevent DNS rebinding attacks.

**Verdict:** GCP metadata SSRF is correctly protected. No changes needed.

---

## Finding 11 — SELinux

**Severity: 🔵 Informational — not applicable**

Ubuntu 24.04 uses AppArmor, not SELinux. No SELinux-related changes needed.

---

## Finding 12 — Time synchronization

**Severity: 🟡 Low — operational hygiene, document only**

Ubuntu 24.04 runs `systemd-timesyncd` by default, synchronized to Ubuntu's NTP pool. Temporal Server requires accurate wall-clock time to schedule activity timeouts and cron workflows correctly; Temporal's documentation recommends < 1 second clock skew between all nodes.

All Temporal nodes here run as containers on the same host, so clock skew between them is zero. The risk is host-level NTP drift.

`timesyncd` provides adequate accuracy for single-host deployments. Cloud VMs (GCE, EC2, DigitalOcean) additionally receive hypervisor-level clock corrections.

**Recommendation:** Add to `DEPLOY.md` under "Production Deployment Notes":

```
Temporal requires accurate system time (< 1 s skew). Verify systemd-timesyncd
is running: `timedatectl status` should show "NTP service: active" and
"System clock synchronized: yes". For bare-metal hosts, consider chrony.
```

---

## Finding 13 — DNS resolver / systemd-resolved

**Severity: 🟠 Medium — latent failure on some Ubuntu 24 configurations**

Ubuntu 24.04 ships `systemd-resolved` listening on the stub address `127.0.0.53:53`. Docker Engine reads `/etc/resolv.conf` to determine the DNS server it injects into containers.

On Ubuntu 24.04, `/etc/resolv.conf` is a symlink to `/run/systemd/resolve/stub-resolv.conf` which contains `nameserver 127.0.0.53`. Docker cannot use this address from inside container network namespaces because `127.0.0.53` is a host loopback address that is not reachable from inside a container bridge network.

Docker Engine handles this in two ways:
1. If Docker detects `127.0.0.53`, it falls back to Google's `8.8.8.8` and `8.8.4.4`.
2. The operator can symlink to the "uplink" resolver: `sudo ln -sf /run/systemd/resolve/resolv.conf /etc/resolv.conf`.

The `docker-compose.yml` does not specify a `dns:` directive on any service, relying on Docker's default injection. Docker's automatic fallback to 8.8.8.8 is generally reliable but:
- Fails in air-gapped or corporate environments where 8.8.8.8 is blocked.
- May resolve differently than the host in split-horizon DNS setups (common in GCP, AWS VPCs).

**Recommendation 1:** Add to `DEPLOY.md` under "Prerequisites" or "Troubleshooting":

```
Ubuntu 24.04 DNS: verify Docker can resolve external names from containers.
  docker run --rm busybox nslookup google.com
If this fails, point /etc/resolv.conf at the real upstream resolver:
  sudo ln -sf /run/systemd/resolve/resolv.conf /etc/resolv.conf
Then restart Docker: sudo systemctl restart docker
```

**Recommendation 2:** For GCE/AWS deployments in private VPCs, add to the `helix-network` definition in `docker-compose.yml`:

```yaml
networks:
  helix-network:
    driver: bridge
    driver_opts:
      com.docker.network.bridge.name: helix0
    # Uncomment to use a specific DNS server (e.g., GCP internal resolver):
    # dns:
    #   - 169.254.169.254  # GCP metadata DNS — only if not using SSRF guard for outbound webhooks
```

Note that adding `169.254.169.254` as a DNS server is safe because DNS queries are outbound from the container; the SSRF guard only blocks HTTP/webhook targets.

---

## Finding 14 — Firewall (ufw)

**Severity: 🟡 Low — DEPLOY.md already has correct guidance**

`DEPLOY.md` already includes the correct `ufw` commands:

```bash
ufw allow 22/tcp
ufw allow 3000/tcp
ufw allow 8000/tcp
ufw enable
```

Ubuntu 24.04 ships `ufw` inactive by default. The existing guidance is correct and complete.

One gap: `DEPLOY.md` does not mention that `ufw` and Docker can conflict. Docker modifies `iptables`/`nftables` rules directly, bypassing `ufw`. A `ufw deny 8000/tcp` rule will **not** block access to the backend if Docker has published port 8000 with `DOCKER-USER` chain rules.

**Recommendation:** Add to `DEPLOY.md` under the firewall section:

```
Note: Docker bypasses ufw by writing directly to iptables/nftables. ufw rules
do NOT restrict ports published by Docker. To restrict access to backend port
8000 to specific source IPs, use ufw's DOCKER-USER chain integration or bind
the port to a specific interface:
  BACKEND_HOST_PORT=127.0.0.1:8000  # only local / reverse-proxy reachable
```

---

## Consolidated action items

| Priority | Item | File to change |
|----------|------|----------------|
| 🔴 High | Document Docker CE (official repo) install; update `setup.sh` error message to reference correct package | `DEPLOY.md`, `setup.sh` |
| 🟠 Medium | Add iptables-nft detection + warning to `setup.sh` preflight | `setup.sh` |
| 🟠 Medium | Add `loginctl enable-linger` guidance for non-root service accounts | `DEPLOY.md` |
| 🟠 Medium | Add DNS stub-resolver troubleshooting note | `DEPLOY.md` |
| 🟡 Low | Add time sync requirement note | `DEPLOY.md` |
| 🟡 Low | Add ufw/Docker bypass note | `DEPLOY.md` |
| 🟡 Low | Add host-Node note for dev builds | `DEPLOY.md` |
| 🔵 Info | Document host Python not required | `DEPLOY.md` |
| 🔵 Info | PostgreSQL 16 client alignment confirmed — no change | — |
| 🔵 Info | SSRF guard for GCE metadata confirmed correct | — |
| 🔵 Info | AppArmor `docker-default` profile — no change needed | — |
| 🔵 Info | cgroup v2 fully compatible — no change needed | — |

---

## Notes on lockfile Python version mismatch

`backend/requirements.lock` and `worker/requirements.lock` were both generated with Python 3.13 (per `pip-compile` header) but the Dockerfiles install them into `python:3.11-slim`. Resolved package versions can differ between Python minor versions (especially for packages with `python_requires` markers). This is not Ubuntu 24-specific but increases the risk of silent dependency drift. The lock files should be regenerated with `python:3.11` to match the runtime.
