"""Claude Code hooks: what the session learns at start and on each prompt (decision 0006).

A hook never fails the session: on any problem it prints a short note or nothing and exits 0.
"""

import json
import os
import sys
from typing import Any

from coloqo import focus
from coloqo.api import Api, ColoqoError, NotLoggedIn, Project
from coloqo.render import topic_line

LOGIN_HINT = (
    "Coloqo plugin is installed, but this computer is not logged in to Coloqo. If the user wants "
    "to use Coloqo, they run `uvx coloqo login` in a terminal (or `! uvx coloqo login` here) "
    "and confirm the code in the browser, then restart the session."
)


def _input() -> dict[str, Any]:
    """Return the hook's JSON input from standard input; empty when there is none."""
    try:
        return json.loads(sys.stdin.read() or "{}")
    except ValueError:
        return {}


def session_start() -> None:
    """Register the project's Assistant and tell the session what the server briefs it with.

    A linked project gets Coloqo's rules, its held Topics, the Inbox and the session's focus;
    an unlinked one a single quiet line (decisions 0020, 0021, 0022).
    """
    data = _input()
    api = Api(timeout=8)
    try:
        api.register(Project.detect(os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd")))
        briefing = api.request("GET", "/briefing")
        unread = api.request("GET", "/inbox") if briefing.get("team_id") else []
    except NotLoggedIn:
        print(LOGIN_HINT)
        return
    except ColoqoError as error:
        print(f"Coloqo is unreachable right now ({error}); its tools may fail.")
        return
    finally:
        api.close()
    lines = [briefing["text"]]
    if briefing.get("team_id"):
        current = focus.load(data.get("session_id"))
        if unread:
            lines.append(f"Inbox — {len(unread)} topics with unread messages:")
            lines.extend(f"- {topic_line(t)}" for t in unread[:10])
            lines.append("Mention them to the user; read with the coloqo read_topic tool.")
        lines.append(
            f"This session's Coloqo focus: {current.describe()} (what reaches it unasked; the "
            "user changes it with /coloqo:focus or by asking you to call set_focus)."
        )
    print("\n".join(lines))


def user_prompt_submit() -> None:
    """Remind the session of Topics addressed to the user that its focus lets through."""
    data = _input()
    current = focus.load(data.get("session_id"))
    if current.mode == "quiet":
        return
    api = Api(timeout=3)
    try:
        api.register(Project.detect(os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd")))
        unread = api.request("GET", "/inbox")
    except ColoqoError:
        return
    finally:
        api.close()
    addressed = [t for t in unread if t.get("addressed")]
    if current.mode == "mine":
        addressed = [t for t in addressed if t.get("holder_assistant_id") == api.assistant_id]
    elif current.mode == "people":
        people = {p.lower() for p in current.people}
        addressed = [t for t in addressed if str(t.get("created_by") or "").lower() in people]
    if addressed:
        lines = ["Coloqo — unread messages addressed to your user:"]
        lines.extend(f"- {topic_line(t)}" for t in addressed[:5])
        lines.append("Mention them briefly in your answer; read with read_topic when relevant.")
        print("\n".join(lines))


HOOKS = {"session-start": session_start, "user-prompt-submit": user_prompt_submit}
