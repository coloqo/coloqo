"""The ``coloqo`` command."""

import argparse
import json
import platform
import sys
import time
import webbrowser

from coloqo import __version__
from coloqo.api import LINK_FILE, Api, ColoqoError, Project
from coloqo.config import config_dir, forget_token, save_token, server_url


def build_parser() -> argparse.ArgumentParser:
    """Build the parser of the ``coloqo`` command (decision 0011)."""
    parser = argparse.ArgumentParser(
        prog="coloqo",
        description="Connect an AI agent to Coloqo, where a team's assistants work together.",
        epilog="Server: COLOQO_URL (default https://app.coloqo.team). https://github.com/coloqo/coloqo",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", metavar="command")
    login = commands.add_parser(
        "login", help="log this computer in, confirming a code in the browser"
    )
    login.add_argument("--name", help="name of this installation (default: the host name)")
    login.add_argument("--no-browser", action="store_true", help="do not open the browser")
    commands.add_parser("logout", help="forget this computer's Coloqo token")
    commands.add_parser("status", help="show whether this computer is logged in and as whom")
    link = commands.add_parser(
        "link", help="link this project to a Team, confirmed in the browser (decision 0020)"
    )
    link.add_argument("--project", help="project directory (default: the current one)")
    link.add_argument(
        "--write", action="store_true", help="then write .coloqo.json to link the repository"
    )
    link.add_argument("--no-browser", action="store_true", help="do not open the browser")
    commands.add_parser("mcp", help="serve the MCP tools over stdio (started by the agent)")
    hook = commands.add_parser("hook", help="run a Claude Code hook (started by the agent)")
    hook.add_argument("event", choices=["session-start", "user-prompt-submit"])
    watch = commands.add_parser("watch", help="print a line per event (a Claude Code monitor)")
    watch.add_argument("--project", help="project directory (default: the current one)")
    return parser


def login(name: str | None, open_browser: bool) -> int:
    """Log this computer in by a code the human confirms in the browser (decision 0003).

    Args:
        name: Installation name; the host name when omitted.
        open_browser: Try to open the confirmation page.
    """
    api = Api()
    try:
        start = api.request(
            "POST", "/device/start", json={"name": name or platform.node() or "computer"}
        )
        print(
            f"Open {start['verification_uri']} and confirm the code: {start['user_code']}",
            flush=True,
        )
        if open_browser:
            webbrowser.open(start["verification_uri_complete"])
        deadline = time.monotonic() + start["expires_in"]
        while time.monotonic() < deadline:
            time.sleep(start["interval"])
            try:
                result = api.request(
                    "POST", "/device/token", json={"device_code": start["device_code"]}
                )
            except ColoqoError as error:
                if error.status == 400 and str(error) == "authorization_pending":
                    continue
                if error.status == 0:
                    continue
                print(f"Login failed: {error}", file=sys.stderr)
                return 1
            path = save_token(result["token"], result.get("pseudonym"))
            who = result.get("pseudonym") or "you"
            print(f"Logged in to {server_url()} as {who}. Token saved in {path}.")
            return 0
        print("The code expired; run `coloqo login` again.", file=sys.stderr)
        return 1
    except ColoqoError as error:
        print(f"Login failed: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    finally:
        api.close()


def status() -> int:
    """Print whether this computer is logged in and as whom."""
    api = Api()
    try:
        me = api.request("GET", "/me")
    except ColoqoError as error:
        print(f"{server_url()}: {error}")
        return 1
    finally:
        api.close()
    print(f"{server_url()}: logged in as {me['pseudonym'] or '(no name chosen yet)'}")
    print(f"Configuration: {config_dir()}")
    return 0


def link(project_dir: str | None, write: bool, open_browser: bool) -> int:
    """Link the project's Assistant to a Team the person picks in the browser.

    Waits up to ten minutes for the choice. With ``write``, then writes ``.coloqo.json`` so
    that the repository links every teammate's project to the same Team.

    Args:
        project_dir: The project; the current directory when omitted.
        write: Write the link file after linking.
        open_browser: Try to open the page.
    """
    project = Project.detect(project_dir)
    api = Api()
    try:
        api.register(project)
        mine = api.request("GET", f"/assistants/{api.assistant_id}")
        if mine["team_id"] is None:
            page = f"{api.url}/assistants/{api.assistant_id}/link"
            print(f"Open {page} and pick the Team for «{mine['name']}».", flush=True)
            if open_browser:
                webbrowser.open(page)
            deadline = time.monotonic() + 600
            while mine["team_id"] is None and time.monotonic() < deadline:
                time.sleep(3)
                mine = api.request("GET", f"/assistants/{api.assistant_id}")
            if mine["team_id"] is None:
                print("No Team was picked; run `coloqo link` again.", file=sys.stderr)
                return 1
        print(f"«{mine['name']}» is linked to «{mine['team']}».")
        if write:
            path = Project.directory(project_dir) / LINK_FILE
            path.write_text(
                json.dumps({"team_id": mine["team_id"], "team": mine["team"]}, ensure_ascii=False)
                + "\n",
                encoding="utf-8",
            )
            print(f"Wrote {path}; commit it to link the repository for the whole Team.")
        return 0
    except ColoqoError as error:
        print(f"Linking failed: {error}", file=sys.stderr)
        return 1
    except OSError as error:
        print(f"Could not write the link file: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    finally:
        api.close()


def main(argv: list[str] | None = None) -> int:
    """Run the command; without arguments print the help.

    Args:
        argv: Command-line arguments without the program name; ``sys.argv[1:]`` when omitted.

    Raises:
        SystemExit: On ``--version`` and ``--help`` (exit code 0) and on an unknown argument
            (exit code 2), raised by ``argparse``.
    """
    for stream in (sys.stdout, sys.stderr):
        # Windows pipes default to the ANSI code page; the agent reads UTF-8.
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "login":
        return login(args.name, not args.no_browser)
    if args.command == "logout":
        print("Logged out." if forget_token() else "This computer was not logged in.")
        return 0
    if args.command == "status":
        return status()
    if args.command == "link":
        return link(args.project, args.write, not args.no_browser)
    if args.command == "mcp":
        from coloqo.mcp_server import run

        run()
        return 0
    if args.command == "hook":
        from coloqo.hooks import HOOKS

        HOOKS[args.event]()
        return 0
    if args.command == "watch":
        from coloqo.watch import watch

        try:
            watch(args.project)
        except KeyboardInterrupt:
            return 0
        return 0
    parser.print_help()
    return 0
