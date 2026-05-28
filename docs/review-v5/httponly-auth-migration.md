# SC-010 — HttpOnly-cookie auth migration (full fix)

Stops storing the JWT in `localStorage` (XSS-readable). The token is now issued
as an `HttpOnly; Secure; SameSite=Strict` cookie (`helix_token`) that JS cannot
read. Bearer-header auth is **fully preserved** so the Python/TS SDKs and CLI
are unaffected. This is an additive change: no URL paths or response schemas
change, and the login/first-admin/refresh bodies still return `access_token`.

---

## Backend changes

### `backend/app/auth/jwt.py`
- `security = HTTPBearer(auto_error=False)` — the bearer header is now optional,
  so a cookie-only browser request is not rejected with 403 before the cookie
  is inspected.
- New `AUTH_COOKIE_NAME = "helix_token"`.
- New `extract_token(request, credentials)` resolves the JWT with **header-wins
  precedence**: `Authorization: Bearer` first (SDK/CLI/programmatic), then the
  `helix_token` cookie (browser). Raises **401** when neither is present (was a
  403 from the old required `HTTPBearer()`; both satisfy existing tests that
  assert `in (401, 403)` for missing auth).
- `get_current_user_id` now calls `extract_token(...)` then `decode_access_token`.
  The SC-036 scope check, SC-012 impersonation attribution, and revocation are
  unchanged, so the SSE-ticket scope rejection still works exactly as before.

### `backend/app/api/auth.py`
- `_bearer = HTTPBearer(auto_error=False)`; all `.credentials` access routed
  through `extract_token` so logout/refresh/sse-ticket work via cookie too.
- New `_set_auth_cookie(response, request, token)` sets `helix_token` with
  `httponly=True`, `secure=(APP_ENV=="production" or request.url.scheme=="https")`,
  `samesite="strict"`, `max_age=JWT_ACCESS_TOKEN_EXPIRE_MINUTES*60`, `path="/"`.
- `POST /auth/login`, `POST /auth/first-admin`, `POST /auth/refresh` now inject
  `response: Response` and call `_set_auth_cookie(...)` **and still return**
  `{access_token, token_type}` in the body.
- `POST /auth/logout` revokes the resolved token and `response.delete_cookie("helix_token", path="/")`.
- `POST /auth/sse-ticket` resolves the minting bearer via `extract_token` (so a
  browser mints the ticket via the cookie) and still returns `{ticket, expires_in}`.

### `backend/app/main.py` — CORS reversal (SC-035 → SC-010)
- `allow_credentials=True` (was `False`). Cookie auth from the browser is a
  credentialed cross-origin request, which requires this. The CORS spec forbids
  `allow_credentials=True` + wildcard origin, so `allow_origins` stays an EXACT
  allowlist: `settings.CORS_ORIGINS` (prod = `FRONTEND_URL`; `config.py` already
  rejects `*` / any regex when `APP_ENV=production`) plus the dev localhost
  regex. Code comment records that this **supersedes SC-035** now that HttpOnly
  cookies are in use, and that **`SameSite=Strict` provides the CSRF protection**
  that motivated SC-035.

---

## How the SDK / CLI bearer path is preserved
- `extract_token` checks the `Authorization` header **first** and returns its
  value verbatim; the cookie is consulted only when the header is absent.
- The test client (`backend/tests/conftest.py`) sends `Authorization` headers on
  every request — that path is unchanged and still fully tested.
- Login/first-admin/refresh still return the token in the JSON body, which is
  what the SDKs/CLI read to build `Authorization: Bearer`.

---

## Frontend changes

### Auth source of truth — `frontend/src/lib/auth-context.tsx`
- No more `localStorage`. On mount, `GET /auth/me` with `credentials:"include"`
  → 200 sets `user`, else unauthenticated.
- `login` / `setupFirstAdmin`: POST with `credentials:"include"` (backend sets
  cookie), then `/auth/me` to populate `user`, then redirect.
- `logout`: `POST /auth/logout` with `credentials:"include"` (revoke + clear
  cookie), clear local `user`, redirect.
- L-011 cross-tab `storage` listener removed (cookies don't fire `storage`).
- `token` is no longer the JWT. It is a **non-secret in-memory presence hint**
  (`"cookie-session"` when `user` is set, else `null`) so the many legacy
  `if (!token) return` gates keep their "is logged in" semantic. It is **never**
  placed in an `Authorization` header anymore.

### Fetch sites — added `credentials:"include"`, dropped `Authorization` headers
Shared API modules (helpers now ignore the `token` arg, send the cookie):
- `lib/use-api.ts`, `lib/sprints/api.ts` (incl. SSE-ticket mint),
  `lib/workflows/api.ts` (incl. SSE-ticket mint), `lib/artifacts/api.ts`,
  `lib/usage/api.ts`, `lib/schema-drift/api.ts`, `lib/cutovers/api.ts`,
  `lib/dashboard/api.ts`, `lib/migration-templates/api.ts`.

Pages / components with raw `fetch` (header dropped, `credentials:"include"`
added, `if (!token)` gates relaxed to gate on real path params only):
- `app/setup/first-admin/page.tsx` (first-admin + 4 wizard steps)
- `app/projects/page.tsx`, `app/projects/new/page.tsx`, `app/projects/[id]/page.tsx`
- `app/projects/[id]/compliance/page.tsx`, `app/projects/[id]/agents/page.tsx`
- `app/knowledge/page.tsx` (list/search/delete/upload)
- `app/artifacts/[id]/page.tsx` (load/rollback/pair-review)
- `app/developer-workspace/[id]/page.tsx`
- `app/workflows/[id]/replay/page.tsx`
- `app/validation/page.tsx`, `app/marketplace/page.tsx`, `app/connectors/page.tsx`
- `app/settings/page.tsx`
- `app/admin/users/page.tsx`, `app/admin/system-health/page.tsx`,
  `app/admin/audit-logs/page.tsx`, `app/admin/llm-settings/page.tsx`,
  `app/admin/agent-mapping/page.tsx`
- `components/layout/Sidebar.tsx`, `components/SchemaDriftCard.tsx`
- `components/ThemeProvider.tsx` (auth signal switched from `token` to `user`)

Sprint/cutover/dashboard/cost-limits pages were **not edited directly**: they
go through the shared `lib/*/api.ts` modules (now cookie-based) and their
`if (!token)` gates pass via the truthy `"cookie-session"` hint.

### SSE
The EventSource flow is unchanged in shape. The `/auth/sse-ticket` mint now
sends `credentials:"include"` (cookie auth) and still returns the ticket in the
body for the `?token=` EventSource URL. The stream handlers decode the ticket
from the query param exactly as before (no cookie involved on the stream itself,
since EventSource can't send custom headers — the short-TTL scoped ticket model
is preserved).

### Folded-in leftovers
- **UI-029**: `app/projects/[id]/sprints/board/page.tsx:327` — "AGENT" suffix
  `text-ink-4` → `text-ink-3`.
- **UI-026**: `app/knowledge/page.tsx` — raw search `<input>` replaced with the
  shared `<SearchInput>` primitive (`ariaLabel="Search uploaded docs"`).
- **M-017**: deleted dead `lib/api/client.ts` (zero importers confirmed via
  grep) and removed the now-empty `lib/api/` directory. No re-exports existed.

---

## Test status
- `python -m py_compile` clean on `jwt.py`, `auth.py`, `main.py`, `test_auth.py`.
- `app.main` imports successfully (verified after bridging two **pre-existing,
  unrelated** local-env dep gaps — see Risks). `security.auto_error == False`
  and `AUTH_COOKIE_NAME == "helix_token"` confirmed at runtime; the auth router
  builds (FastAPI validates the `response: Response` injection at registration).
- `npx tsc --noEmit` — **green**.
- Added two backend tests (no existing assertion weakened; the bearer-header
  path remains fully tested):
  - `test_login_sets_httponly_cookie_and_cookie_auth_works` — login sets an
    HttpOnly/SameSite=Strict cookie, body still returns the token, and a
    header-less `/auth/me` authenticates via the cookie.
  - `test_logout_clears_cookie` — logout (via cookie) clears the cookie.
- The full pytest suite could not run locally: it needs Postgres
  (`postgresql://helix:helix_password@localhost:5432/helix_test`) and the same
  pre-existing dep gaps block conftest import. Run on cloud.

---

## Risks to verify on cloud
1. **Cross-origin cookie behaviour.** If the frontend and backend are on
   different sites (e.g. `app.example.com` ↔ `api.example.com`), the browser
   sends the cookie cross-origin only with `credentials:"include"` (done) AND
   `allow_credentials=True` + an exact origin echo (done). Confirm
   `CORS_ORIGINS`/`FRONTEND_URL` lists the EXACT frontend origin in prod, or the
   browser will silently drop the cookie / block the response.
2. **`SameSite=Strict` vs cross-site frontend.** With Strict, the browser will
   NOT attach `helix_token` on a top-level navigation that originates from a
   different site. For a same-site SPA (XHR/fetch after the app is loaded) this
   is fine, but if login redirects arrive from a truly different site, consider
   whether `Lax` is needed. Verify the login → dashboard redirect still carries
   the cookie in the target deployment topology.
3. **Secure flag on non-HTTPS.** `secure` is set when `APP_ENV=="production"` OR
   the request is HTTPS. A prod deployment served over plain HTTP would set a
   Secure cookie the browser refuses to send — ensure prod is HTTPS (it is,
   behind Caddy; `X-Forwarded-Proto` is reflected into `request.url.scheme`).
4. **CSRF.** `SameSite=Strict` is the primary CSRF defence (replaces SC-035's
   `allow_credentials=False`). State-changing endpoints have no separate CSRF
   token; confirm Strict is acceptable for the threat model, or add a
   double-submit token if any cross-site POST scenario is required.
5. **Token TTL / refresh.** The cookie `max_age` matches the JWT expiry. There
   is no silent refresh loop; when the cookie expires the next `/auth/me` 401s
   and the UI returns to unauthenticated. Verify expiry UX on cloud.
6. **Pre-existing local-env dep gaps (NOT introduced here):**
   `python-json-logger` 2.0.7 installed but `logging_config.py` uses the 3.x
   `from pythonjsonlogger import json` API; `email-validator` missing; `agents/`
   not on `sys.path` outside pytest. These block a bare local `import app.main`
   but are upstream of all auth code and resolved by the locked cloud deps.
