# DEPLOY_GCP_NETWORK — GCP single-VM network & configuration audit

> Generated 2026-05-26. Scope: Docker Compose port bindings, `setup.sh`
> network logic, `.env.example` network-related variables, `docs/deployment/INSTALLATION.md`,
> and `backend/app/security/ssrf.py`. Focus is deploying the Helix stack
> on a single GCP Compute Engine VM (e2-standard-4 or similar) behind a
> reserved external IP.
>
> Severity legend: 🔴 CRITICAL · 🟠 HIGH · 🟡 MED · 🔵 LOW

---

## 1. Port-binding audit (docker-compose.yml)

| Service | Internal port | Host binding | Verdict |
|---|---|---|---|
| `postgres` | 5432 | **none** — no `ports:` block | Correct: internal only |
| `redis` | 6379 | **none** — no `ports:` block | Correct: internal only |
| `temporal` | 7233 | **none** — no `ports:` block | Correct: internal only |
| `temporal-ui` | 8080 | `${TEMPORAL_UI_BIND:-127.0.0.1}:${TEMPORAL_UI_HOST_PORT:-8233}:8080` (profile=debug only) | Acceptable: loopback default, opt-in profile |
| `backend` | 8000 | `${BACKEND_HOST_PORT:-8000}:8000` | **Problem** — see GCP-001 |
| `worker` | (none) | **none** | Correct: no inbound port |
| `frontend` | 3000 | `${FRONTEND_HOST_PORT:-3000}:3000` | **Problem** — see GCP-002 |

---

## 2. Findings

### 2.1 Port exposure

🔴 **GCP-001 — Backend port 8000 is published to `0.0.0.0` on the host.**

`docker-compose.yml` line 120: `"${BACKEND_HOST_PORT:-8000}:8000"`. No
bind-address is specified, so Docker binds on all interfaces (`0.0.0.0`).
On a GCP VM this means the FastAPI process is reachable on the VM's
external IP at port 8000 if the GCP firewall rule is opened, and even
without a firewall rule it is reachable from inside the VPC by other
machines. The API includes `/docs` (OpenAPI), `/metrics` (Prometheus),
`/api/v1/superadmin/*`, and full CRUD — none of which should be public.

`docs/deployment/INSTALLATION.md` "Production Deployment Notes" says
"Restrict PostgreSQL and Redis to private networks" but says nothing
about backend 8000. `docs/review-v2/REVIEW_INFRA.md` INFRA-045 already
flagged that `DEPLOY.md` incorrectly advises `ufw allow 8000/tcp`; that
root cause is the compose file not restricting the bind address.

**Immediate fix (compose):**
```yaml
ports:
  - "${BACKEND_BIND:-127.0.0.1}:${BACKEND_HOST_PORT:-8000}:8000"
```
Then the reverse proxy (Caddy/nginx) on the same host reaches the backend
via `http://127.0.0.1:8000` and port 8000 is never reachable externally.

**GCP firewall:** do NOT open port 8000 in the firewall rule. Only 80,
443, and 22 (or IAP SSH) should be open.

---

🟠 **GCP-002 — Frontend port 3000 is published to `0.0.0.0`.**

Same issue as GCP-001 but for Next.js on port 3000. The frontend should
also be restricted to loopback and fronted by the reverse proxy:

```yaml
ports:
  - "${FRONTEND_BIND:-127.0.0.1}:${FRONTEND_HOST_PORT:-3000}:3000"
```

The GCP firewall should not open port 3000 directly. The reverse proxy
terminates TLS on 443 and proxies to `http://127.0.0.1:3000`.

---

### 2.2 GCP firewall rules

🟠 **GCP-003 — No documented GCP firewall ruleset.**

Neither `docs/deployment/INSTALLATION.md` nor any operator doc specifies
the required GCP firewall rules for a production single-VM deployment.
The recommended minimal ruleset is in section 4 below.

---

### 2.3 `NEXT_PUBLIC_API_URL` and hostname detection

🔴 **GCP-004 — `NEXT_PUBLIC_API_URL` defaults to `http://localhost:8000` and is baked at Next.js build time.**

`.env.example` line 63: `NEXT_PUBLIC_API_URL=http://localhost:8000`. In
the Docker build pipeline (`docker-compose.build.yml`) this value is
passed as a build argument and embedded in the compiled JS bundle — it
cannot be overridden at container start time.

On GCP, `localhost:8000` is unreachable from the user's browser. The
operator **must** set this to the public hostname or IP before running
`docker compose build` (or `setup.sh`). There is no mechanism that
autodetects the external IP, no prompt in `setup.sh`, and no error if
the value is still `localhost` when building for production.

**Fix A (recommended): add GCP IMDS autodetect to `setup.sh`:**
```bash
# In setup.sh, before build step, after .env is provisioned:
if grep -q 'NEXT_PUBLIC_API_URL=http://localhost' .env 2>/dev/null; then
  # Attempt GCP external IP detection (skipped silently if not on GCP)
  # NOTE: this curl runs on the HOST, not inside a container; it is NOT
  # gated by the in-app SSRF guard. The metadata endpoint is intentionally
  # accessible here.
  EXT_IP=$(curl -s --max-time 2 \
    -H "Metadata-Flavor: Google" \
    "http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip" \
    2>/dev/null || true)
  if [ -n "$EXT_IP" ]; then
    warn "Detected GCP external IP: ${EXT_IP}"
    warn "Setting NEXT_PUBLIC_API_URL=https://${EXT_IP} (update to your domain before production)."
    sed -i "s|^NEXT_PUBLIC_API_URL=.*|NEXT_PUBLIC_API_URL=https://${EXT_IP}|" .env
  fi
fi
```

**Fix B:** document prominently at the top of `setup.sh` that the operator
must set `NEXT_PUBLIC_API_URL=https://<their-domain>` in `.env` before
running `setup.sh --rebuild`.

Note: the GCP metadata URL `metadata.google.internal` is explicitly in the
SSRF denylist in `security/ssrf.py` (see GCP-007). That guard protects
webhook delivery — it is correct behavior there. The setup-script IP
detection is a separate code path that runs as a shell command on the host
before any container starts; it does not pass through the SSRF guard and
requires no changes to `ssrf.py`.

---

### 2.4 TLS

🔴 **GCP-005 — No TLS configuration exists anywhere in the stack.**

The project has no Caddy, nginx, or Traefik service in `docker-compose.yml`.
No `Caddyfile`, no nginx conf, no cert management script. `INSTALLATION.md`
says "Use TLS through a reverse proxy" but provides no implementation.

Without TLS:
- Browser will block `NEXT_PUBLIC_API_URL` if `https://` is set and the
  backend cert is self-signed.
- `CORS_ORIGINS` cannot use `https://` in production.
- JWT tokens and API keys travel in plaintext.
- Modern browsers block `Set-Cookie; SameSite=Strict` over plain HTTP.

**Recommended fix:** add a `caddy` service to `docker-compose.yml` (see
section 5 for snippet). Caddy is the most operator-friendly choice: it
obtains and renews Let's Encrypt certs automatically, proxies to both
backend and frontend, and handles SSE buffering correctly.

The alternative (GCP HTTPS load balancer) is preferred for larger deploys
but costs ~$18/month and requires more GCP configuration; document as
"Option B" for ops teams.

---

### 2.5 CORS configuration

🟠 **GCP-006 — `CORS_ORIGINS` default is `["http://localhost:3000"]`; production override is undocumented for GCP.**

`.env.example` line 55: `CORS_ORIGINS=["http://localhost:3000"]`. In
production on GCP, this will cause every browser API call to be rejected
with CORS error because the browser hits `https://helix.example.com` but
the backend only allows `http://localhost:3000`.

The config validator (`backend/app/core/config.py` line 103) blocks `*`
wildcards in production and also blocks `CORS_ORIGIN_REGEX` in production
(line 106-107) — this is correct. But there is no guidance that the
operator MUST update `CORS_ORIGINS` to exactly match the frontend's public
origin before deployment.

The code defaults in `config.py` line 53 include `"http://localhost:8080"` in
addition to `"http://localhost:3000"` — this extra origin is not in
`.env.example`, which is confusing.

**Fix:** add a note in `.env.example`:
```bash
# GCP / production: must match your actual frontend origin.
# Example: CORS_ORIGINS=["https://helix.example.com"]
# Must rebuild frontend if NEXT_PUBLIC_API_URL changes (it is baked at build time).
CORS_ORIGINS=["http://localhost:3000"]
```

And add a check in `setup.sh` that warns if `APP_ENV=production` and
`CORS_ORIGINS` still contains `localhost`.

---

### 2.6 SSRF guard and GCE IMDS

🟢 **GCP-007 — `security/ssrf.py` correctly blocks GCE IMDS `169.254.169.254`.**

`ssrf.py` lines 27-32: `_FORBIDDEN_HOSTS` set includes both
`"metadata.google.internal"` and `"169.254.169.254"`, plus
`"fd00:ec2::254"` (AWS IPv6 IMDS). The `_is_forbidden_ip` check also
catches `169.254.169.254` via `ip.is_link_local`. This is double-defense
and correct.

The SSRF guard is applied at webhook creation and webhook delivery. It
correctly prevents a malicious operator from creating a webhook pointing
at the instance metadata service to exfiltrate service-account tokens.

**No action required** for the SSRF guard itself.

🔵 **GCP-008 — SSRF guard does not cover `100.100.100.200` (Alibaba Cloud IMDS) or `fd00:ec2::254` double-check for IPv6.**

`fd00:ec2::254` is listed in `_FORBIDDEN_HOSTS` (good), but the
`_is_forbidden_ip` function will catch any private/link-local IPv6 anyway.
For completeness, consider adding the Alibaba Cloud IMDS `100.100.100.200`
(which is a routable address and NOT caught by `is_link_local` or
`is_private`). Not a GCP-specific issue; low priority.

---

### 2.7 Health endpoint exposure

🟠 **GCP-009 — `/api/v1/health`, `/api/v1/readyz`, and `/metrics` are all served on the same port 8000 with no auth.**

`health.py` serves `/health` (liveness) and `/readyz` (readiness) with no
authentication — this is correct for the probe itself. The GCP Load
Balancer backend health check probe requires the path to return 200 without
auth.

However:
- `/metrics` (Prometheus) on port 8000 is also unauthenticated. It exposes
  process metrics, memory usage, and HTTP route-level stats. This should
  not be publicly reachable.
- Since GCP-001 has port 8000 exposed on `0.0.0.0` by default, `/metrics`
  is currently publicly accessible.

**Fix:** after GCP-001 is resolved (bind 8000 to 127.0.0.1), this is
automatically mitigated because only the reverse proxy can reach port 8000.
If the GCP HTTPS LB is used as the health-check prober instead of a
co-located nginx, a separate internal port or network tag firewall rule
should gate the `/readyz` access from the LB probe IP range only
(`130.211.0.0/22` and `35.191.0.0/16` for GCP health checkers).

The correct GCP LB health check path is `/api/v1/readyz` (returns 503
when DB is down, 200 when ready). `/api/v1/health` is the liveness probe
(never reaches DB).

---

### 2.8 WebSocket / SSE proxy

🟠 **GCP-010 — SSE streaming endpoint exists but no reverse-proxy configuration handles it.**

`backend/app/api/agent_workflows.py` implements a Server-Sent Events
stream at `GET /api/v1/workflows/{id}/stream` (auth via query-string
`?token=`). SSE connections are long-lived HTTP/1.1 responses with
`Content-Type: text/event-stream`.

Standard nginx and some GCP Load Balancer configurations buffer all
responses by default, which causes SSE frames to be held until the buffer
fills, breaking real-time streaming. The current stack has no proxy, so
this is a latent issue.

**Fix (nginx):** in any nginx upstream block for the backend, add:
```nginx
proxy_buffering        off;
proxy_cache            off;
proxy_read_timeout     300s;
proxy_send_timeout     300s;
X-Accel-Buffering      no;
```

**Fix (Caddy):** Caddy disables response buffering for `text/event-stream`
automatically when using the `reverse_proxy` directive with default
settings. No extra configuration is required — this is a significant
reason to prefer Caddy for this project.

**Fix (GCP HTTPS LB):** GCP's external HTTPS load balancer buffers
responses at the CDN layer. SSE will not work through it directly.
Mitigation options:
1. Use a GCP backend service with `enableCDN: false` for the API backend.
2. Run nginx/Caddy on the VM as the termination point and use the GCP LB
   only for TCP passthrough (L4 LB), letting Caddy handle TLS.
3. For production: use GCP Serverless NEGs or Cloud Run if WebSocket/SSE
   scale is needed.

---

### 2.9 MTU

🔵 **GCP-011 — GCP VPC default MTU 1460 vs Docker bridge default 1500.**

GCP VPC uses a default MTU of **1460** bytes (not 1500) due to IP-in-IP
encapsulation overhead. Docker's default bridge MTU is 1500. This mismatch
can cause silent packet fragmentation and TCP slowness for larger payloads
(artifact uploads, LLM streaming responses).

**Fix:** add `--mtu 1460` to the `helix-network` bridge in `docker-compose.yml`:
```yaml
networks:
  helix-network:
    driver: bridge
    driver_opts:
      com.docker.network.driver.mtu: "1460"
```

This is a low-risk, high-value change for GCP deployments. On non-GCP
environments 1460 is also safe (all hosts on the internet accept 1460-byte
frames). Note: if the operator uses Google Cloud VPN or Interconnect,
the effective MTU may be lower (1376 for IPsec); set accordingly.

---

### 2.10 GCP egress and LLM API costs

🟡 **GCP-012 — LLM provider egress costs are not documented.**

The stack makes outbound HTTPS calls to LLM providers (OpenAI
`api.openai.com`, Anthropic `api.anthropic.com`, Google `generativelanguage.googleapis.com`,
etc.) from the GCP VM. These are GCP **egress** bytes.

GCP egress pricing (as of 2026):
- **Within same region** (e.g., GCE → Google APIs): effectively free for
  Google APIs; $0.01-0.08/GB for non-Google destinations.
- **Internet egress** (to OpenAI/Anthropic): $0.08-0.12/GB depending on
  region and volume tier.
- A typical LLM migration analysis session exchanging 100k tokens ≈ 400 KB
  of payload. At $0.08/GB, 1 TB/month ≈ $80/month egress only.

For operators using **Google Vertex AI** (Gemini via the Vertex API), all
API calls stay within Google's private network — zero egress cost if the
VM is in the same project/region. This is a meaningful cost optimization
for high-volume migration deployments.

**Recommendation for operators:** document in `docs/deployment/INSTALLATION.md`
that for production GCP deployments where cost matters:
1. Place the VM in the same region as your Vertex AI endpoint.
2. Use Cloud NAT for other egress (prevents needing a public IP on the
   VM for egress; only the LB IP is public).
3. Enable VPC Flow Logs to monitor actual egress volume.

---

### 2.11 VPC peering

🔵 **GCP-013 — VPC peering not relevant for single-VM deploy.**

All services run in one Docker Compose network on one VM. VPC peering
(connecting two GCP VPC networks) is irrelevant unless the operator wants
to peer a managed Cloud SQL or Memorystore (Redis) instance into the same
VPC. If the operator migrates from local Postgres/Redis to Cloud SQL/
Memorystore, document the VPC peering or Private Service Connect steps
separately. Not a current blocker.

---

### 2.12 GCP Service Account

🟡 **GCP-014 — GCP Service Account strategy not documented; two viable paths exist.**

The stack may need GCP credentials for:
1. **GCS artifact storage** (if `ARTIFACT_STORAGE_PROVIDER=s3` with a
   GCS bucket via the S3-compatible XML API).
2. **Vertex AI** as an LLM provider.
3. **Cloud Pub/Sub** (future webhook fanout).
4. **Secret Manager** (future key management).

Currently `.env.example` documents `S3_BUCKET`, `S3_REGION`, `AWS_ACCESS_KEY_ID`
etc. but says nothing about GCP auth.

**Option A — Credentials in `.env` (simple, less secure):**
```bash
GOOGLE_APPLICATION_CREDENTIALS=/run/secrets/gcp-sa.json
```
Mount the SA JSON file as a Docker secret or a volume. Works everywhere.
Risk: SA key is a long-lived credential; if `.env` or the volume is
compromised, the key is exposed.

**Option B — Workload Identity (recommended for production):**
1. Create a GCP service account for the Helix VM.
2. Bind the SA to the VM instance: `gcloud compute instances set-service-account`.
3. The SA's access token is served by the GCE metadata server at
   `http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token`.
4. Application Default Credentials (ADC) in the container picks it up
   automatically without any key file or env var.
5. **SSRF guard note:** the backend's `ssrf.py` blocks
   `metadata.google.internal` for webhook URLs — correct. ADC
   inside the `google-auth` library hits the metadata server directly
   via the OS network stack (not via the SSRF guard), so workload
   identity works with no changes to `ssrf.py`.

Add a section to `docs/deployment/INSTALLATION.md`:
```
## GCP Service Account
Option A: mount credentials file + set GOOGLE_APPLICATION_CREDENTIALS
Option B (recommended): assign a service account to the VM instance and
use Application Default Credentials; no key file required.
```

---

### 2.13 Static IP

🟠 **GCP-015 — No guidance on reserving a GCP static external IP.**

GCP VM instances are assigned an **ephemeral** external IP by default.
When the VM is stopped and restarted, the IP changes. If operators set
`NEXT_PUBLIC_API_URL=http://34.x.x.x` (the ephemeral IP) and later
stop/start the VM, the frontend bundle is broken (wrong IP baked in).

**Required step before go-live:**
```bash
# Reserve a static regional IP
gcloud compute addresses create helix-vm-ip \
  --region=us-central1 \
  --network-tier=PREMIUM

# Assign it to the VM
gcloud compute instances delete-access-config INSTANCE_NAME \
  --access-config-name="External NAT"
gcloud compute instances add-access-config INSTANCE_NAME \
  --access-config-name="External NAT" \
  --address=STATIC_IP_ADDRESS
```

Document this in `setup.sh` step 0 or in `INSTALLATION.md`. Without a
static IP, TLS certificates (Let's Encrypt via Caddy) also break on each
IP change.

---

### 2.14 Domain and DNS A record

🟡 **GCP-016 — No operator instructions for domain + DNS setup.**

The stack assumes the operator has a domain (e.g. `helix.example.com`)
but provides no instructions for:
1. Pointing the domain's A record at the reserved GCP external IP.
2. Waiting for DNS propagation before running `setup.sh` (Caddy's ACME
   challenge fails if DNS hasn't propagated).
3. Setting `NEXT_PUBLIC_API_URL=https://helix.example.com` and
   `CORS_ORIGINS=["https://helix.example.com"]` in `.env`.
4. Rebuilding the frontend image after the URL change.

Recommended addition to `INSTALLATION.md`:
```
## GCP Domain Setup
1. Reserve a static external IP (see GCP-015 above).
2. Create an A record: helix.example.com → STATIC_IP (TTL 300).
3. Wait for DNS propagation (check: `dig helix.example.com`).
4. Update .env:
   NEXT_PUBLIC_API_URL=https://helix.example.com
   CORS_ORIGINS=["https://helix.example.com"]
   FRONTEND_URL=https://helix.example.com
5. Run: ./setup.sh --rebuild
```

---

### 2.15 `setup.sh` network-related gaps

🟡 **GCP-017 — `setup.sh` probes `http://localhost:${BACKEND_HOST_PORT:-8000}/api/v1/readyz` which assumes port 8000 is accessible from the host.**

After GCP-001 is fixed (bind backend to 127.0.0.1), this probe continues
to work because `127.0.0.1:8000` is still reachable from the host. No
change needed.

However, `setup.sh` prints a summary block with hardcoded `localhost` URLs:
```
Frontend   http://localhost:3000
Backend    http://localhost:8000
```
On a GCP VM these are meaningless to the operator who accesses the
service from a browser. The summary block should auto-detect and print the
actual public hostname/IP (same detection as GCP-004 above).

🟡 **GCP-018 — `setup.sh` has no GCP-specific pre-flight section.**

Unlike `--down` and `--nuke` shortcuts, there is no `--gcp` mode that:
1. Reserves a static IP (or verifies one is attached).
2. Autodetects `EXTERNAL_IP` and validates/updates `.env`.
3. Checks that the GCP firewall allows only 80/443/22.
4. Recommends Caddy installation.

This could be a separate `scripts/gcp-preflight.sh` rather than
modifying `setup.sh`.

---

## 3. INSTALLATION.md audit

🟠 **GCP-019 — `docs/deployment/INSTALLATION.md` shows stale URLs.**

Line 26-29 shows `Frontend: http://localhost:8080`, `Backend: http://localhost:8000`,
`Temporal UI: http://localhost:8233`. The actual compose defaults are
frontend on port 3000 (not 8080) and temporal-ui on 8233 bound to
127.0.0.1. The documentation is stale and will mislead operators on a
fresh GCP install.

🟡 **GCP-020 — `docs/deployment/INSTALLATION.md` example `DATABASE_URL` embeds `helix_password`.**

Line 38: `DATABASE_URL=postgresql://helix:helix_password@postgres:5432/helix_metadata`.
This hardcoded example password will inevitably end up in a real `.env`
if an operator copies it without reading carefully. The comment should
say `helix:<POSTGRES_PASSWORD from generate-secrets.sh>` instead.

---

## 4. Recommended GCP firewall rules

For a single-VM deployment where Caddy (or nginx) terminates TLS on the VM:

```bash
# Allow HTTPS from internet
gcloud compute firewall-rules create helix-allow-https \
  --direction=INGRESS \
  --priority=1000 \
  --network=default \
  --action=ALLOW \
  --rules=tcp:443 \
  --source-ranges=0.0.0.0/0 \
  --target-tags=helix-vm

# Allow HTTP from internet (for ACME challenge + redirect to HTTPS)
gcloud compute firewall-rules create helix-allow-http \
  --direction=INGRESS \
  --priority=1000 \
  --network=default \
  --action=ALLOW \
  --rules=tcp:80 \
  --source-ranges=0.0.0.0/0 \
  --target-tags=helix-vm

# Allow SSH via GCP IAP (preferred — no public SSH port needed)
gcloud compute firewall-rules create helix-allow-iap-ssh \
  --direction=INGRESS \
  --priority=1000 \
  --network=default \
  --action=ALLOW \
  --rules=tcp:22 \
  --source-ranges=35.235.240.0/20 \
  --target-tags=helix-vm

# If using GCP HTTPS Load Balancer health checks (only needed for LB path):
gcloud compute firewall-rules create helix-allow-lb-health \
  --direction=INGRESS \
  --priority=1000 \
  --network=default \
  --action=ALLOW \
  --rules=tcp:8000 \
  --source-ranges=130.211.0.0/22,35.191.0.0/16 \
  --target-tags=helix-vm

# Block everything else (implicit GCP deny — no action needed, but explicit
# for clarity if the operator has other permissive rules):
# DO NOT open: 3000, 5432, 6379, 7233, 8000, 8233, 8080
```

Tag the VM at creation: `--tags=helix-vm`

**Summary: only ports 80, 443, and 22 (IAP) should be open to 0.0.0.0/0.**
Port 8000 (backend) must never be open to the public internet.

---

## 5. Recommended reverse-proxy snippet (Caddy — preferred)

Add a `caddy` service to `docker-compose.yml`. Caddy auto-obtains Let's
Encrypt certs, handles SSE correctly without extra config, and proxies to
both backend and frontend.

**`caddy/Caddyfile` (create at `deploy/caddy/Caddyfile`):**
```caddyfile
{
    # Uncomment for staging/testing to avoid Let's Encrypt rate limits:
    # acme_ca https://acme-staging-v02.api.letsencrypt.org/directory
    email {$CADDY_ADMIN_EMAIL}
}

{$PUBLIC_HOSTNAME} {
    # Frontend — Next.js
    handle /* {
        reverse_proxy frontend:3000 {
            # Required for Next.js streaming / SSR
            header_up Host {http.request.host}
        }
    }

    # Backend API (all /api/* routes go to FastAPI)
    handle /api/* {
        reverse_proxy backend:8000 {
            # SSE: Caddy automatically disables buffering for text/event-stream.
            # No extra directives needed.
            header_up Host {http.request.host}
            header_up X-Forwarded-Proto https
            header_up X-Real-IP {http.request.remote.host}
        }
    }

    # OpenAPI docs (keep accessible; restrict with auth if needed)
    handle /docs* {
        reverse_proxy backend:8000
    }

    # Prometheus metrics — restrict to internal monitoring network
    # Uncomment the remote_ip matcher to lock down /metrics:
    # @monitoring remote_ip 10.0.0.0/8 127.0.0.1
    # handle @monitoring /metrics {
    #     reverse_proxy backend:8000
    # }
    handle /metrics {
        # Block public access to Prometheus metrics
        respond 403
    }

    # Security headers
    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
        X-Content-Type-Options nosniff
        X-Frame-Options DENY
        Referrer-Policy strict-origin-when-cross-origin
    }
}
```

**Addition to `docker-compose.yml`:**
```yaml
  caddy:
    image: caddy:2.8-alpine
    container_name: helix-caddy
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
      - "443:443/udp"   # HTTP/3
    environment:
      PUBLIC_HOSTNAME: ${PUBLIC_HOSTNAME:?PUBLIC_HOSTNAME is required — set to your domain}
      CADDY_ADMIN_EMAIL: ${CADDY_ADMIN_EMAIL:?CADDY_ADMIN_EMAIL is required for Let's Encrypt}
    volumes:
      - ./deploy/caddy/Caddyfile:/etc/caddy/Caddyfile:ro
      - helix_caddy_data:/data
      - helix_caddy_config:/config
    depends_on:
      backend:
        condition: service_healthy
      frontend:
        condition: service_started
    networks:
      - helix-network
    deploy:
      resources:
        limits:
          memory: 128M
```

Add to `volumes:`:
```yaml
  helix_caddy_data:
    driver: local
  helix_caddy_config:
    driver: local
```

After adding the caddy service, change backend and frontend port bindings
to loopback-only (see GCP-001/GCP-002 fixes above). Add
`PUBLIC_HOSTNAME` and `CADDY_ADMIN_EMAIL` to `.env.example`.

**Nginx alternative snippet (if Caddy is not preferred):**
```nginx
server {
    listen 80;
    server_name helix.example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name helix.example.com;

    ssl_certificate     /etc/letsencrypt/live/helix.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/helix.example.com/privkey.pem;

    # Frontend
    location / {
        proxy_pass         http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade $http_upgrade;
        proxy_set_header   Connection 'upgrade';
        proxy_set_header   Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # Backend API
    location /api/ {
        proxy_pass         http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-Proto https;

        # Required for SSE (text/event-stream) — disables nginx response buffering
        proxy_buffering    off;
        proxy_cache        off;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
        add_header         X-Accel-Buffering no;
    }

    # Block Prometheus metrics from public access
    location /metrics {
        deny all;
    }
}
```

---

## 6. Aggregate severity counts

| Severity | Count | Items |
|---|---|---|
| 🔴 CRITICAL | 3 | GCP-001, GCP-004, GCP-005 |
| 🟠 HIGH | 7 | GCP-002, GCP-003, GCP-006, GCP-009, GCP-010, GCP-015, GCP-019 |
| 🟡 MED | 8 | GCP-012, GCP-014, GCP-016, GCP-017, GCP-018, GCP-020, GCP-011 (if deploying on GCP), GCP-016 |
| 🔵 LOW | 3 | GCP-008, GCP-011, GCP-013 |

---

## 7. Verdict

The current compose file is **not safe to deploy directly on a public GCP VM
without modification**. The three CRITICAL issues are:

1. **Backend port 8000 bound to `0.0.0.0`** (GCP-001): anyone who opens the
   firewall or misconfigures it exposes the full API, admin endpoints, OpenAPI
   docs, and Prometheus metrics to the public internet.

2. **`NEXT_PUBLIC_API_URL` defaults to `localhost` with no GCP autodetect**
   (GCP-004): the frontend bundle baked at build time will call the wrong host
   and the app will silently fail for all users.

3. **No TLS configuration** (GCP-005): credentials, JWTs, and API keys travel
   in plaintext. Browsers will reject mixed-content and same-site cookie
   restrictions.

The SSRF guard (`security/ssrf.py`) is **correctly implemented** for the GCE
IMDS — no changes needed there. Internal services (Postgres, Redis, Temporal)
are correctly not published to the host in the production compose file.

**Minimum viable GCP hardening checklist (do before first user touches the system):**

- [ ] Reserve a static external IP and attach to VM.
- [ ] Create DNS A record for your domain pointing to the static IP.
- [ ] Add `caddy` service to `docker-compose.yml` (see section 5).
- [ ] Change backend and frontend `ports:` to `127.0.0.1:` bind (GCP-001/002).
- [ ] Set `NEXT_PUBLIC_API_URL=https://helix.example.com` in `.env` BEFORE building.
- [ ] Set `CORS_ORIGINS=["https://helix.example.com"]` in `.env`.
- [ ] Set `FRONTEND_URL=https://helix.example.com` in `.env`.
- [ ] Set `PUBLIC_HOSTNAME=helix.example.com` and `CADDY_ADMIN_EMAIL=ops@example.com` in `.env`.
- [ ] Add `com.docker.network.driver.mtu: "1460"` to `helix-network` driver_opts.
- [ ] Set GCP firewall: allow only 80/443/22(IAP); deny 3000/5432/6379/7233/8000/8233.
- [ ] Run `./setup.sh --rebuild` after all `.env` changes.
- [ ] Verify `/api/v1/readyz` returns 200 through the Caddy proxy over HTTPS.
- [ ] Verify SSE stream at `/api/v1/workflows/{id}/stream` delivers events in real time (no buffering).

---

*End of DEPLOY_GCP_NETWORK.md*
