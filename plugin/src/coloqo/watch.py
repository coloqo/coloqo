"""The watch: holds the event stream and prints a line per event for this Assistant.

Claude Code runs it as a plugin monitor; each printed line reaches the session as a
notification (decision 0006). An event is a signal: the Assistant reads the content with
its tools.
"""

import json
import time
from collections.abc import Iterator
from typing import Any

import httpx

from coloqo import focus
from coloqo.api import Api, ColoqoError, NotLoggedIn, Project
from coloqo.hooks import LOGIN_HINT

SILENCE_SECONDS = 45
"""No event and no heartbeat for this long means the connection is dead (decision 0006)."""

NOTICE_AFTER_SECONDS = 180
"""A break longer than this is reported to the session once the stream is back."""


def say(line: str) -> None:
    """Print one notification line for the session.

    Args:
        line: The text.
    """
    print(line, flush=True)


def frames(lines: Iterator[str]) -> Iterator[tuple[str | None, str, dict[str, Any]]]:
    """Parse Server-Sent Events into ``(id, event, data)``.

    Args:
        lines: Lines of the stream without line ends.
    """
    event_id, kind, data = None, "message", []
    for line in lines:
        if not line:
            if data:
                try:
                    payload = json.loads("\n".join(data))
                except ValueError:
                    payload = {}
                yield event_id, kind, payload
            event_id, kind, data = None, "message", []
        elif line.startswith("id:"):
            event_id = line[3:].strip()
        elif line.startswith("event:"):
            kind = line[6:].strip()
        elif line.startswith("data:"):
            data.append(line[5:].lstrip())


def describe(kind: str, data: dict[str, Any], user_id: int, assistant_id: int) -> str | None:
    """Return the line for an event, or ``None`` when it does not concern this Assistant.

    Args:
        kind: Event kind.
        data: Event data.
        user_id: This Assistant's User.
        assistant_id: This Assistant.
    """
    topic = f"{data.get('ref')} «{data.get('title')}»"
    to_me = data.get("to_assistant_id") == assistant_id or (
        data.get("to_user_id") == user_id and data.get("to_assistant_id") is None
    )
    if kind == "topic":
        if data.get("author_assistant_id") == assistant_id:
            return None
        if to_me:
            return (
                f"Coloqo: {data.get('author')} opened {topic} in Area «{data.get('area')}» "
                f"addressed to you — read_topic {data.get('ref')}"
            )
        return (
            f"Coloqo: new topic {topic} in Area «{data.get('area')}» by {data.get('author')} — "
            f"read_topic {data.get('ref')} if it concerns your work."
        )
    if kind == "message":
        if data.get("author_assistant_id") == assistant_id or data.get("number") == 1:
            # The opening Message comes with its Topic's event.
            return None
        if data.get("kind") in ("stage", "closed"):
            # Stage lines are for the web and read_topic; closing comes as topic_status.
            return None
        involved = assistant_id in (data.get("assistant_ids") or [])
        if not (to_me or (involved and data.get("to_user_id") in (None, user_id))):
            return None
        author = data.get("assistant") or f"{data.get('author')} (human)"
        target = " to you" if to_me else ""
        return (
            f"Coloqo: {topic} — message #{data.get('number')} from {author}{target}. "
            f"read_topic {data.get('ref')} after={int(data.get('number') or 1) - 1}"
        )
    if kind == "topic_status" and data.get("automatic"):
        return f"Coloqo: {topic} was closed for inactivity; writing in it reopens it."
    if kind == "topic_status" and data.get("holder_assistant_id") == assistant_id:
        if data.get("author_assistant_id") == assistant_id:
            return None
        outcome = f": {data['outcome']}" if data.get("outcome") else ""
        return f"Coloqo: {topic} was {data.get('status')} by {data.get('author')}{outcome}."
    if kind == "topic_idle":
        return (
            f"Coloqo: {topic} closes for inactivity on {str(data.get('closes_at'))[:10]}. If "
            "the work goes on, note_stage; if it is done, close_topic with the outcome."
        )
    return None


def watch(project_dir: str | None = None) -> None:
    """Hold the event stream for the project's Assistant until the session ends.

    Waits quietly while the computer is not logged in, and reconnects after breaks with the
    last event id, so nothing is missed (decision 0006).

    Args:
        project_dir: The project; Claude Code's project or the current directory when omitted.
    """
    project = Project.detect(project_dir)
    last_id: str | None = None
    hinted = False
    broken_since: float | None = None
    delay = 1.0
    while True:
        api = Api(timeout=10)
        try:
            api.register(project)
            user_id = api.request("GET", "/me")["id"]
            assistant_id = api.assistant_id
            assert assistant_id is not None
            headers = {"Last-Event-ID": last_id} if last_id else {}
            timeout = httpx.Timeout(10, read=SILENCE_SECONDS)
            with api.http.stream("GET", "/api/events", headers=headers, timeout=timeout) as stream:
                if stream.status_code == 401:
                    raise NotLoggedIn(401, "revoked")
                stream.raise_for_status()
                for event_id, kind, data in frames(stream.iter_lines()):
                    if kind == "ready":
                        if broken_since and time.monotonic() - broken_since > NOTICE_AFTER_SECONDS:
                            minutes = int((time.monotonic() - broken_since) // 60)
                            say(
                                f"Coloqo: connection restored after {minutes} min; check the inbox."
                            )
                        broken_since, delay, hinted = None, 1.0, False
                        continue
                    if event_id:
                        last_id = event_id
                    line = describe(kind, data, user_id, assistant_id)
                    if line and focus.allows(focus.load(), kind, data, assistant_id):
                        say(line)
        except NotLoggedIn:
            if not hinted:
                say(LOGIN_HINT)
                hinted = True
            delay = 60.0
        except (ColoqoError, httpx.HTTPError):
            broken_since = broken_since or time.monotonic()
            delay = min(delay * 2, 60.0)
        finally:
            api.close()
        time.sleep(delay)
