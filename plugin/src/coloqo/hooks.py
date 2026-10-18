"""Claude Code hooks: what the session learns at start and on each prompt (decision 0006).

A hook never fails the session: on any problem it prints a short note or nothing and exits 0.
"""

import json
import os
import sys
from typing import Any

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
    """Register the project's Assistant and tell the session who it is and what is unread."""
    data = _input()
    api = Api(timeout=8)
    try:
        name = api.register(Project.detect(os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd")))
        teams = api.request("GET", "/teams")
        unread = api.request("GET", "/inbox")
    except NotLoggedIn:
        print(LOGIN_HINT)
        return
    except ColoqoError as error:
        print(f"Coloqo is unreachable right now ({error}); its tools may fail.")
        return
    finally:
        api.close()
    lines = [
        f"Coloqo: you are the Assistant «{name}» in Coloqo, where your user's Team's assistants "
        "work together. Teams: " + (", ".join(f"«{t['name']}»" for t in teams) or "none yet") + "."
    ]
    if unread:
        lines.append(f"Inbox — {len(unread)} topics with unread messages:")
        lines.extend(f"- {topic_line(t)}" for t in unread[:10])
        lines.append("Mention them to the user; read with the coloqo read_topic tool.")
    print("\n".join(lines))


def user_prompt_submit() -> None:
    """Remind the session of Topics with unread messages addressed to the user."""
    _input()
    api = Api(timeout=3)
    try:
        unread = api.request("GET", "/inbox")
    except ColoqoError:
        return
    finally:
        api.close()
    addressed = [t for t in unread if t.get("addressed")]
    if addressed:
        lines = ["Coloqo — unread messages addressed to your user:"]
        lines.extend(f"- {topic_line(t)}" for t in addressed[:5])
        lines.append("Mention them briefly in your answer; read with read_topic when relevant.")
        print("\n".join(lines))


HOOKS = {"session-start": session_start, "user-prompt-submit": user_prompt_submit}
