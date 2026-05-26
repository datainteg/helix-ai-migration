"""Helix CLI entrypoint.

Stdlib `argparse` so the install footprint stays tiny — only httpx beyond
the standard library.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from helix_cli import __version__
from helix_cli.client import HelixClient


def _print(value: Any) -> None:
    if isinstance(value, (dict, list)):
        print(json.dumps(value, indent=2, default=str))
    else:
        print(value)


def _cmd_login(client: HelixClient, args: argparse.Namespace) -> None:
    import getpass
    password = args.password or getpass.getpass("Password: ")
    if args.api:
        client.api_url = args.api.rstrip("/")
    out = client.login(args.email, password)
    print(f"Logged in as {args.email}. Token saved to ~/.helix/config.json.")
    if args.verbose:
        _print({"token_len": len(out.get("access_token", "")), "token_type": out.get("token_type")})


def _cmd_whoami(client: HelixClient, _args: argparse.Namespace) -> None:
    _print(client.whoami())


def _cmd_logout(client: HelixClient, _args: argparse.Namespace) -> None:
    client.logout()
    print("Logged out.")


def _cmd_projects_list(client: HelixClient, _args: argparse.Namespace) -> None:
    rows = client.list_projects()
    if not rows:
        print("No projects.")
        return
    for p in rows:
        print(f"{p.get('id', '')[:36]:36}  {p.get('status', ''):10}  {p.get('name', '')}")


def _cmd_projects_new(client: HelixClient, args: argparse.Namespace) -> None:
    out = client.create_project(args.name, args.description or "")
    _print(out)


def _cmd_workflow_start(client: HelixClient, args: argparse.Namespace) -> None:
    out = client.start_workflow(args.project, args.requirement_id, args.requirement_text or "")
    _print(out)


def _cmd_workflow_status(client: HelixClient, args: argparse.Namespace) -> None:
    _print(client.workflow_status(args.workflow_id))


def _cmd_workflow_list(client: HelixClient, args: argparse.Namespace) -> None:
    rows = client.list_workflows(project_id=args.project)
    for r in rows:
        print(f"{r.get('workflow_id', '')[:36]:36}  {r.get('status', ''):16}  {r.get('mode', ''):12}  {r.get('created_at', '')}")


def _cmd_cost_summary(client: HelixClient, args: argparse.Namespace) -> None:
    _print(client.cost_summary(days=args.days))


def _cmd_cost_limit(client: HelixClient, _args: argparse.Namespace) -> None:
    _print(client.cost_limit())


def _cmd_templates_list(client: HelixClient, _args: argparse.Namespace) -> None:
    rows = client.list_templates()
    for t in rows:
        print(f"{t['id']:30}  {t['source']:12} → {t['target']:12}  risk={t['risk_level']}")


def _cmd_templates_clone(client: HelixClient, args: argparse.Namespace) -> None:
    _print(client.clone_template(args.template_id, args.project_name))


def _cmd_cutover_list(client: HelixClient, args: argparse.Namespace) -> None:
    rows = client.list_cutovers(args.project)
    for c in rows:
        print(f"{c['id'][:36]:36}  {c['state']:14}  {c['source_ref']} → {c['target_ref']}")


def _cmd_cutover_transition(client: HelixClient, args: argparse.Namespace) -> None:
    _print(client.transition_cutover(args.cutover_id, args.target_state, args.notes or ""))


# ── admin bootstrap ────────────────────────────────────────────────────────────

_SENTINEL_FILE = Path(".helix-bootstrap")


def _read_sentinel() -> dict[str, str]:
    """Read creds written by setup.sh into .helix-bootstrap (key=value lines)."""
    if not _SENTINEL_FILE.exists():
        return {}
    cfg: dict[str, str] = {}
    for line in _SENTINEL_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        cfg[k.strip()] = v.strip()
    return cfg


def _cmd_admin_bootstrap(client: HelixClient, args: argparse.Namespace) -> int:
    """helix admin bootstrap — create the first super-admin user headlessly.

    Exit codes:
      0  success (or already bootstrapped — idempotent)
      1  network / unexpected error
      2  auth / validation error from the server
    """
    import getpass as _getpass

    # Override API URL if provided
    if getattr(args, "api", None):
        client.api_url = args.api.rstrip("/")

    # Resolve credentials: flags → sentinel file → interactive
    sentinel = _read_sentinel()

    email = (
        getattr(args, "email", None)
        or os.getenv("HELIX_ADMIN_EMAIL")
        or sentinel.get("ADMIN_EMAIL")
    )
    password = (
        getattr(args, "password", None)
        or os.getenv("HELIX_ADMIN_PASSWORD")
        or sentinel.get("ADMIN_PASSWORD")
    )
    org_name = (
        getattr(args, "org_name", None)
        or os.getenv("HELIX_ORG_NAME")
        or sentinel.get("ORG_NAME")
        or "Helix"
    )
    display_name = (
        getattr(args, "display_name", None)
        or os.getenv("HELIX_ADMIN_NAME")
        or sentinel.get("ADMIN_NAME")
        or "Admin"
    )

    if not email:
        print("error: --email is required (or set HELIX_ADMIN_EMAIL)", file=sys.stderr)
        return 2

    # Password: try --password-stdin, then flag, then prompt
    if getattr(args, "password_stdin", False):
        password = sys.stdin.readline().rstrip("\n")
    elif not password:
        password = _getpass.getpass(f"Password for {email}: ")

    if not password:
        print("error: password is required", file=sys.stderr)
        return 2

    # TOS acceptance gate
    if not getattr(args, "accept_tos", False) and not sentinel.get("ACCEPT_TOS"):
        print(
            "error: you must pass --accept-tos to confirm acceptance of the "
            "Helix terms of service before bootstrapping.",
            file=sys.stderr,
        )
        return 2

    # Derive org slug from org_name
    import re
    org_slug = re.sub(r"[^a-z0-9]+", "-", org_name.lower()).strip("-") or "helix"

    try:
        result = client.bootstrap_first_admin(
            email=email,
            password=password,
            name=display_name,
            org_name=org_name,
            org_slug=org_slug,
        )
        token_len = len(result.get("access_token", ""))
        print(
            f"Bootstrap complete. Admin user {email!r} created. "
            f"Token saved to ~/.helix/config.json (length={token_len})."
        )
        return 0
    except RuntimeError as exc:
        msg = str(exc)
        if msg == "already bootstrapped":
            print("Already bootstrapped — first admin exists. Nothing to do.")
            return 0
        # 401/403 → exit 2; network/other → exit 1
        print(f"error: {msg}", file=sys.stderr)
        if msg.startswith(("401", "403", "400")):
            return 2
        return 1


# ── helix install (one-liner wrapper) ─────────────────────────────────────────


def _cmd_install(client: HelixClient, args: argparse.Namespace) -> int:
    """helix install — run setup.sh then bootstrap the first admin.

    One-liner:
        pipx install helix-cli && helix install --domain helix.example.com \\
            --admin-email ops@example.com

    The command:
      1. Verifies setup.sh is present in the current working directory.
      2. Runs ./setup.sh with any extra flags passed via --setup-flags.
      3. Waits for the backend to be reachable (inherits setup.sh readyz gate).
      4. Runs `helix admin bootstrap` with the supplied credentials.
    """
    setup_script = Path("setup.sh")
    if not setup_script.exists():
        print(
            "error: setup.sh not found in the current directory. "
            "Run this command from the cloned helix-ai-migration repo root.",
            file=sys.stderr,
        )
        return 1

    domain = getattr(args, "domain", None) or ""
    admin_email = getattr(args, "admin_email", None) or ""
    admin_password = getattr(args, "admin_password", None) or ""
    org_name = getattr(args, "org_name", None) or "Helix"
    setup_flags = getattr(args, "setup_flags", None) or []

    # Build setup.sh invocation
    cmd = ["/bin/bash", "setup.sh"] + setup_flags
    if domain:
        # Pass domain as env-var hint; setup.sh reads NEXT_PUBLIC_API_URL
        env = {
            **os.environ,
            "NEXT_PUBLIC_API_URL": f"https://{domain}",
            "CORS_ORIGINS": f'["https://{domain}"]',
            "FRONTEND_URL": f"https://{domain}",
            "PUBLIC_HOSTNAME": domain,
        }
    else:
        env = None

    print(f"Running ./setup.sh{' ' + ' '.join(setup_flags) if setup_flags else ''} ...")
    try:
        ret = subprocess.call(cmd, env=env)
    except OSError as exc:
        print(f"error: could not run setup.sh: {exc}", file=sys.stderr)
        return 1
    if ret != 0:
        print(f"error: setup.sh exited with code {ret}", file=sys.stderr)
        return 1

    # Determine API URL
    api_url = f"https://{domain}" if domain else "http://localhost:8000"
    client.api_url = api_url

    # Synthesise a fake Namespace for bootstrap
    bootstrap_ns = argparse.Namespace(
        api=api_url,
        email=admin_email or None,
        password=admin_password or None,
        password_stdin=False,
        org_name=org_name,
        display_name="Admin",
        accept_tos=True,
    )
    print("Running admin bootstrap ...")
    return _cmd_admin_bootstrap(client, bootstrap_ns)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="helix", description="Helix Migration CLI")
    p.add_argument("--version", action="version", version=f"helix {__version__}")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    # login
    sp = sub.add_parser("login", help="Authenticate and save token to ~/.helix/config.json")
    sp.add_argument("--api", help="API base URL (default: HELIX_API_URL or http://localhost:8000)")
    sp.add_argument("--email", required=True)
    sp.add_argument("--password", help="Password (omit to prompt)")
    sp.set_defaults(func=_cmd_login)

    sub.add_parser("whoami", help="Show the current authenticated user").set_defaults(func=_cmd_whoami)
    sub.add_parser("logout", help="Revoke the saved token and clear local config").set_defaults(func=_cmd_logout)

    # projects
    proj = sub.add_parser("projects", help="Project commands")
    proj_sub = proj.add_subparsers(dest="proj_cmd", required=True)
    proj_sub.add_parser("list").set_defaults(func=_cmd_projects_list)
    np = proj_sub.add_parser("new")
    np.add_argument("--name", required=True)
    np.add_argument("--description")
    np.set_defaults(func=_cmd_projects_new)

    # workflow
    wf = sub.add_parser("workflow", help="Workflow commands")
    wf_sub = wf.add_subparsers(dest="wf_cmd", required=True)
    ws = wf_sub.add_parser("start")
    ws.add_argument("--project", required=True)
    ws.add_argument("--requirement-id", required=True)
    ws.add_argument("--requirement-text")
    ws.set_defaults(func=_cmd_workflow_start)
    wst = wf_sub.add_parser("status")
    wst.add_argument("workflow_id")
    wst.set_defaults(func=_cmd_workflow_status)
    wl = wf_sub.add_parser("list")
    wl.add_argument("--project", help="If omitted, lists every workflow in the org")
    wl.set_defaults(func=_cmd_workflow_list)

    # cost
    cost = sub.add_parser("cost", help="LLM cost commands")
    cost_sub = cost.add_subparsers(dest="cost_cmd", required=True)
    cs = cost_sub.add_parser("summary")
    cs.add_argument("--days", type=int, default=30)
    cs.set_defaults(func=_cmd_cost_summary)
    cost_sub.add_parser("limit").set_defaults(func=_cmd_cost_limit)

    # templates
    tpl = sub.add_parser("templates", help="Migration templates")
    tpl_sub = tpl.add_subparsers(dest="tpl_cmd", required=True)
    tpl_sub.add_parser("list").set_defaults(func=_cmd_templates_list)
    tc = tpl_sub.add_parser("clone")
    tc.add_argument("--template-id", required=True)
    tc.add_argument("--project-name", required=True)
    tc.set_defaults(func=_cmd_templates_clone)

    # cutover
    cut = sub.add_parser("cutover", help="Cutover state machine")
    cut_sub = cut.add_subparsers(dest="cut_cmd", required=True)
    cl = cut_sub.add_parser("list")
    cl.add_argument("--project", required=True)
    cl.set_defaults(func=_cmd_cutover_list)
    ct = cut_sub.add_parser("transition")
    ct.add_argument("cutover_id")
    ct.add_argument("target_state", choices=["bulk", "tail", "freeze", "diff", "flip", "done", "rolled_back"])
    ct.add_argument("--notes")
    ct.set_defaults(func=_cmd_cutover_transition)

    # admin
    adm = sub.add_parser("admin", help="Administrative commands (no auth token required for bootstrap)")
    adm_sub = adm.add_subparsers(dest="adm_cmd", required=True)
    bs = adm_sub.add_parser(
        "bootstrap",
        help=(
            "Create the first super-admin user. Reads .helix-bootstrap sentinel "
            "file if no flags are given. Idempotent: exits 0 if already done."
        ),
    )
    bs.add_argument("--api", help="API base URL (default: HELIX_API_URL or http://localhost:8000)")
    bs.add_argument("--email", help="Admin email address (or set HELIX_ADMIN_EMAIL)")
    bs.add_argument(
        "--password",
        help="Admin password (omit to prompt, or use --password-stdin)",
    )
    bs.add_argument(
        "--password-stdin",
        dest="password_stdin",
        action="store_true",
        help="Read password from stdin (first line only). Useful for scripts.",
    )
    bs.add_argument("--org-name", dest="org_name", default=None, help="Organisation display name (default: Helix)")
    bs.add_argument("--display-name", dest="display_name", default=None, help="Admin user display name (default: Admin)")
    bs.add_argument(
        "--accept-tos",
        dest="accept_tos",
        action="store_true",
        help="Confirm acceptance of the Helix terms of service. Required.",
    )
    bs.set_defaults(func=_cmd_admin_bootstrap)

    # install
    inst = sub.add_parser(
        "install",
        help=(
            "One-command install: run ./setup.sh then bootstrap the first admin. "
            "Example: pipx install helix-cli && helix install "
            "--domain helix.example.com --admin-email ops@example.com"
        ),
    )
    inst.add_argument("--domain", help="Public hostname (e.g. helix.example.com). Sets NEXT_PUBLIC_API_URL.")
    inst.add_argument("--admin-email", dest="admin_email", help="First admin email address")
    inst.add_argument("--admin-password", dest="admin_password", help="First admin password (omit to prompt)")
    inst.add_argument("--org-name", dest="org_name", default="Helix", help="Organisation display name")
    inst.add_argument(
        "--setup-flags",
        dest="setup_flags",
        nargs="*",
        default=[],
        help="Extra flags forwarded to setup.sh (e.g. --rebuild)",
    )
    inst.set_defaults(func=_cmd_install)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    client = HelixClient()
    try:
        result = args.func(client, args)
        # Commands that manage their own exit codes return an int.
        if isinstance(result, int):
            return result
        return 0
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
