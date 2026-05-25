"""Helix CLI entrypoint.

Stdlib `argparse` so the install footprint stays tiny — only httpx beyond
the standard library.
"""

from __future__ import annotations

import argparse
import json
import sys
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

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    client = HelixClient()
    try:
        args.func(client, args)
        return 0
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
