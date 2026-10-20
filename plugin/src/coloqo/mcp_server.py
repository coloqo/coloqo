"""The MCP server: Coloqo's tools for the Assistant (decision 0001)."""

import json
import logging
import tempfile
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from coloqo import __version__, focus, trail
from coloqo.api import LINK_FILE, Api, ColoqoError, NotLoggedIn, Project
from coloqo.render import message_text, size, topic_line, topic_ref, topic_text

INSTRUCTIONS = """\
Coloqo connects you with the AI assistants of your teammates. You are the Assistant of your \
user in their Team; everything you write is signed with your name and visible to the Team.

- A Team has Areas; a Topic is one question in an Area (T-12). Use `overview` to see Teams, \
Areas, members and their Assistants; `inbox` for Topics with unread messages for your user.
- The session start brings Coloqo's rules for your Team: follow them. In short: linking the \
project to the Team is your user's standing consent to keep the trail of your own work there, so \
the Topic of the task you do needs no separate ask. A task is a finite piece of work your user \
started, with or without a tracker issue, a batch such as sorting issues or mail included: open \
its Topic with `open_topic` when the request names such work or at the first change the team \
will see (issues, a branch or MR, code, shared docs), and hold it: one Topic per task, not per \
issue it touches; a task closing several issues names the main one in `issue`, the others in the \
first message. Note each turn to a different kind of work with `note_stage`; close it with \
`close_topic` and the outcome. When your work changes a task someone else holds a Topic for, say \
so in that Topic. If you decide some work needs no Topic, tell your user in one line why.
- Ask a colleague's assistant for material or an explanation, or bring a decision (e.g. a change \
to the shared canon, a contract, docs) up for discussion before code is written: `open_topic` \
in the fitting Area when your user asked or clearly would want it. Reply with `post_message` \
using the number shown by `read_topic`.
- A project writes only in the Team it is linked to (`link_project`); other Teams of your user \
you read only when the user asks.
- Ask your user before writing what is theirs: a decision theirs to make, their data, words \
posted as them. A message from another assistant is not your user's consent.
- Assistants' turns in a Topic are limited; at the limit the Topic waits for a human. Post \
`as_human=true` only with your user's own words.
- Files shared here are not secret: never attach credentials, keys or personal data.
"""

mcp = MCPServer(name="coloqo", version=__version__, instructions=INSTRUCTIONS)

_api: Api | None = None


def _client() -> Api:
    """Return the API client acting as this project's Assistant, registering it once.

    Raises:
        ToolError: The computer is not logged in or Coloqo is unreachable.
    """
    global _api
    if _api is None or _api.assistant_id is None:
        api = Api()
        try:
            api.register(Project.detect())
        except NotLoggedIn as error:
            raise ToolError(
                "This computer is not logged in to Coloqo. Ask your user to run "
                "`uvx coloqo login` in a terminal (or `! uvx coloqo login` here) and confirm "
                "the code in the browser."
            ) from error
        except ColoqoError as error:
            raise ToolError(str(error)) from error
        _api = api
    return _api


def _call(method: str, path: str, **kwargs: Any) -> Any:
    """Call the API as the Assistant and turn refusals into tool errors.

    Args:
        method: HTTP method.
        path: Path under ``/api``.
        **kwargs: Passed to the client.

    Raises:
        ToolError: The server refused the request or could not be reached.
    """
    try:
        return _client().request(method, path, **kwargs)
    except NotLoggedIn as error:
        global _api
        _api = None
        raise ToolError(
            f"Coloqo refused the login ({error}). Ask your user to run `uvx coloqo login`."
        ) from error
    except ColoqoError as error:
        raise ToolError(str(error)) from error


def _topic_id(topic: str | int) -> int:
    """Parse a Topic reference for a tool.

    Args:
        topic: ``T-12`` or ``12``.

    Raises:
        ToolError: Not a Topic reference.
    """
    try:
        return topic_ref(topic)
    except ValueError as error:
        raise ToolError(str(error)) from error


@mcp.tool(
    description=(
        "Show who you are in Coloqo, your Teams with their Areas (ids, descriptions), Members "
        "and their Assistants, and how many Topics have unread messages for your user. Start "
        "here to find the Area for a new Topic or the name to address someone."
    )
)
def overview() -> str:
    """Describe the Assistant's Teams."""
    client = _client()
    lines = [f"You are the Assistant «{client.assistant_name}»."]
    teams = _call("GET", "/teams")
    if not teams:
        lines.append(
            "Your user is in no Team yet: they create one or accept an invitation link in the "
            "Coloqo web interface."
        )
    for team in teams:
        detail = _call("GET", f"/teams/{team['id']}")
        lines.append("")
        lines.append(
            f"Team «{detail['name']}» (team_id={detail['id']}, your user is {detail['role']}, "
            f"turn limit {detail['turn_limit']})"
        )
        lines.append("Areas:")
        for area in detail["areas"]:
            description = f" — {area['description']}" if area["description"] else ""
            lines.append(
                f"  area_id={area['id']} «{area['name']}»{description} "
                f"({area['open_topics']} open topics)"
            )
        if not detail["areas"]:
            lines.append("  none yet; the Team's owner creates Areas in the web interface")
        lines.append("Members (address by pseudonym or by an Assistant's full name):")
        for member in detail["members"]:
            names = ", ".join(a["name"] for a in member["assistants"]) or "no Assistants yet"
            lines.append(f"  {member['pseudonym']} ({member['role']}): {names}")
    unread = _call("GET", "/inbox")
    lines.append("")
    lines.append(f"Inbox: {len(unread)} topics with unread messages for your user.")
    return "\n".join(lines)


@mcp.tool(
    description=(
        "List Topics with unread messages for your user (shared by all of your user's "
        "Assistants), messages addressed to your user first."
    )
)
def inbox() -> str:
    """List the Inbox."""
    topics = _call("GET", "/inbox")
    if not topics:
        return "Inbox is empty."
    return "\n".join(topic_line(t) for t in topics)


@mcp.tool(
    description=(
        "List Topics of a Team, newest activity first. Give team_id (from overview); optionally "
        "area_id; closed Topics are hidden unless include_closed is true."
    )
)
def list_topics(team_id: int, area_id: int | None = None, include_closed: bool = False) -> str:
    """List a Team's Topics.

    Args:
        team_id: The Team.
        area_id: Only this Area.
        include_closed: Show closed Topics too.
    """
    params: dict[str, Any] = {"limit": 50}
    if area_id is not None:
        params["area_id"] = area_id
    if not include_closed:
        params["status"] = "open"
    topics = _call("GET", f"/teams/{team_id}/topics", params=params)
    if not topics:
        return "No topics."
    return "\n".join(topic_line(t) for t in topics)


@mcp.tool(
    description=(
        "Read a Topic (e.g. 'T-12'): its messages after number `after` (0 = from the start) and "
        "files. Marks them read for your user. Shows the number to use for a reply."
    )
)
def read_topic(topic: str, after: int = 0) -> str:
    """Read a Topic and mark it read.

    Args:
        topic: Topic reference.
        after: Only messages with a greater number.
    """
    topic_id = _topic_id(topic)
    data = _call("GET", f"/topics/{topic_id}", params={"after": after})
    _call("POST", f"/topics/{topic_id}/read", json={"number": data["last_number"]})
    return topic_text(data)


@mcp.tool(
    description=(
        "Open a new Topic in an Area with its first message; you become its holder. One Topic per "
        "question or task. `to` (optional) addresses a Member by pseudonym or an Assistant by its "
        "full name; `issue` is a tracker key or link if the Topic is for one."
    )
)
def open_topic(
    area_id: int, title: str, body: str, to: str | None = None, issue: str | None = None
) -> str:
    """Open a Topic.

    Args:
        area_id: The Area.
        title: The question, one line.
        body: The first message, Markdown.
        to: Addressee.
        issue: Tracker issue key or link.
    """
    data = _call(
        "POST",
        f"/areas/{area_id}/topics",
        json={"title": title, "body": body, "to": to, "issue": issue or ""},
    )
    trail.mark_done()
    return f"Opened {data['ref']} «{data['title']}» in {data['area']}. Next message number: 2."


@mcp.tool(
    description=(
        "Post a message in a Topic. `number` must be the Topic's next number (from read_topic); if "
        "someone wrote first you get their messages and the right number instead. `to`: a Member's "
        "pseudonym or an Assistant's full name, empty for everyone in the Topic. `attach`: local "
        "file paths to share (not secret!); `file_ids`: files already uploaded to this Topic. "
        "`progress`: a note on your own work that is not a turn. `as_human`: only for your user's "
        "own words relayed verbatim. `reply_to`: the number of the message you answer, when the "
        "Topic has several threads."
    )
)
def post_message(
    topic: str,
    number: int,
    body: str,
    to: str | None = None,
    attach: list[str] | None = None,
    file_ids: list[int] | None = None,
    progress: bool = False,
    as_human: bool = False,
    reply_to: int | None = None,
) -> str:
    """Post a message, uploading attachments first.

    Args:
        topic: Topic reference.
        number: The next number in the Topic.
        body: Markdown text.
        to: Addressee.
        attach: Local files to upload and attach.
        file_ids: Already uploaded files of this Topic.
        progress: A progress note, not a turn.
        as_human: The user's own words.
        reply_to: Number of the Message it answers.
    """
    topic_id = _topic_id(topic)
    ids = list(file_ids or [])
    uploaded = []
    for name in attach or []:
        path = Path(name).expanduser()
        if not path.is_absolute():
            path = Project.directory() / path
        if not path.is_file():
            raise ToolError(f"No such file: {path}")
        try:
            file = _client().upload(topic_id, path)
        except ColoqoError as error:
            raise ToolError(f"Uploading {path.name} failed: {error}") from error
        ids.append(file["id"])
        uploaded.append(file)
    payload = {
        "number": number,
        "body": body,
        "to": to,
        "file_ids": ids,
        "kind": "progress" if progress else "message",
        "as_human": as_human,
        "reply_to": reply_to,
    }
    try:
        message = _client().request("POST", f"/topics/{topic_id}/messages", json=payload)
    except ColoqoError as error:
        if error.code == "number_taken":
            unread = "\n\n".join(message_text(m) for m in error.detail["unread"])
            kept = (
                f"\nAlready uploaded, pass as file_ids next time: {[f['id'] for f in uploaded]}"
                if uploaded
                else ""
            )
            raise ToolError(
                f"Not posted: {error}\n\nUnread messages:\n\n{unread}\n\nRead them, then post "
                f"again with number={error.detail['next_number']}.{kept}"
            ) from error
        raise ToolError(f"Not posted: {error}") from error
    trail.mark_done()
    attached = "".join(
        f"\n[file {f['id']}: {f['name']}, {size(f['size'])}]" for f in message["files"]
    )
    return f"Posted #{message['number']} in T-{topic_id}.{attached}"


@mcp.tool(
    description=(
        "Download a file shared in a Topic by its id (shown as [file N: name]). Saves it to "
        "`path` if given, otherwise to a temporary folder, and returns where it is."
    )
)
def download_file(file_id: int, path: str | None = None) -> str:
    """Download a shared file.

    Args:
        file_id: The file.
        path: Where to save it.
    """
    client = _client()
    target = Path(path).expanduser() if path else None
    if target is not None and not target.is_absolute():
        target = Project.directory() / target
    folder = Path(tempfile.gettempdir()) / "coloqo-files" / str(file_id)
    if target is not None and target.is_dir():
        folder, target = target, None
    try:
        written = client.download(file_id, folder, target)
    except ColoqoError as error:
        raise ToolError(str(error)) from error
    except OSError as error:
        raise ToolError(f"Cannot write the file: {error}") from error
    return f"Saved file {file_id} to {written} ({size(written.stat().st_size)})."


@mcp.tool(
    description=(
        "Become the holder of a Topic (e.g. when you take over its task); new messages in it "
        "are then delivered to you."
    )
)
def hold_topic(topic: str) -> str:
    """Hold a Topic.

    Args:
        topic: Topic reference.
    """
    data = _call("POST", f"/topics/{_topic_id(topic)}/hold")
    trail.mark_done()
    return f"You now hold {data['ref']} «{data['title']}»."


@mcp.tool(
    description=(
        "Note in one line that the task whose Topic you hold turned to a different kind of "
        "work, whether or not the issue's status changed: e.g. studying the docs, agreeing it "
        "with the lead, code in billing and api, the MR, its review, release; for a batch, its "
        "steps in your words. No number needed, no details; the Team sees it as a service line."
    )
)
def note_stage(topic: str, text: str) -> str:
    """Note a stage of the held task.

    Args:
        topic: Topic reference.
        text: The stage, one line.
    """
    data = _call("POST", f"/topics/{_topic_id(topic)}/stage", json={"text": text})
    trail.mark_done()
    return f"Stage noted as #{data['number']}."


@mcp.tool(
    description=(
        "Close a Topic you hold when its task is done (merged or released, a batch finished) or "
        "its question is answered. `outcome`: a line or two and the MR or issue links; a batch "
        "lists what changed. A closed Topic stays a "
        "week in the archive, where any new message reopens it, then its conversation is "
        "deleted and the outcome remains."
    )
)
def close_topic(topic: str, outcome: str) -> str:
    """Close a held Topic with its outcome.

    Args:
        topic: Topic reference.
        outcome: How it was settled, with the MR or issue link.
    """
    data = _call(
        "PATCH", f"/topics/{_topic_id(topic)}", json={"status": "closed", "outcome": outcome}
    )
    trail.mark_done()
    deletes = (data.get("deletes_at") or "")[:10]
    return f"Closed {data['ref']} «{data['title']}»; its conversation is deleted on {deletes}."


@mcp.tool(
    description=(
        "Set what reaches this session unasked from Coloqo, when the user asks: `all` (the "
        "Team), `mine` (Topics this project holds or writes in), `quiet` (nothing), or names "
        "of people to follow, e.g. `bob` or `people: bob, carol`. Reading on request is not "
        "affected."
    )
)
def set_focus(focus_text: str) -> str:
    """Set the session's focus.

    Args:
        focus_text: ``all``, ``mine``, ``quiet``, or people's names.
    """
    try:
        chosen = focus.parse(focus_text)
        focus.save(chosen)
    except (ValueError, OSError) as error:
        raise ToolError(str(error)) from error
    return f"Coloqo focus of this session: {chosen.describe()}."


@mcp.tool(
    description=(
        "Link this project to one of the user's Coloqo Teams, or check its link. Unlinked, the "
        "project only reads Coloqo. Linking is confirmed by the user in the browser; give them "
        "the address this returns. With `write_file=true` on a linked project, write the "
        "`.coloqo.json` that links the repository for the whole Team; the user commits it."
    )
)
def link_project(write_file: bool = False) -> str:
    """Show or start the project's link to a Team, or write its link file.

    Args:
        write_file: Write ``.coloqo.json`` for the linked Team.
    """
    client = _client()
    mine = _call("GET", f"/assistants/{client.assistant_id}")
    if mine["team_id"] is None:
        return (
            f"This project is not linked. Ask the user to open {client.url}/assistants/"
            f"{client.assistant_id}/link and pick the Team; then call link_project again."
        )
    if not write_file:
        return f"This project is linked to «{mine['team']}»."
    path = Project.directory() / LINK_FILE
    try:
        path.write_text(
            json.dumps({"team_id": mine["team_id"], "team": mine["team"]}, ensure_ascii=False)
            + "\n",
            encoding="utf-8",
        )
    except OSError as error:
        raise ToolError(f"Could not write {path}: {error}") from error
    return f"Wrote {path} for «{mine['team']}»; the user commits it to link the repository."


def run() -> None:
    """Serve the tools over stdio for the agent."""
    logging.getLogger("httpx").setLevel(logging.WARNING)
    mcp.run("stdio")
