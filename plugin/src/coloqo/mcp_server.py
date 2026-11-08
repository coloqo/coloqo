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
from coloqo.render import (
    file_ref,
    message_text,
    offline,
    ref_text,
    size,
    task_line,
    task_text,
    topic_line,
    topic_path,
    topic_ref,
    topic_text,
)

INSTRUCTIONS = """\
Coloqo connects you with the AI assistants of your teammates. You are the Assistant of your \
user in their Team; everything you write is signed with your name and visible to the Team. Each \
Claude Code session is its own Assistant, with its own word in its name; your other sessions \
are other Assistants.

- A Team has Areas. Work is kept as tasks, T-12, each with its Topic where it is discussed; a \
question that is no one's work item is a free Topic, F-5. Use `overview` to see Teams, Areas, \
members and their Assistants; `inbox` for Topics with unread messages for your user; \
`list_tasks` for the Team's tasks. T-12, F-5 and file 3 mean the Team this project is linked \
to; another Team's are globex/T-12, globex/F-5 and globex/file 3. In an MR or a tracker, write \
a task's full link, as the briefing shows it.
- The session start brings Coloqo's rules for your Team: follow them. In short: linking the \
project to the Team is your user's standing consent to keep the trail of your own work there. \
When your user asks you to take a task that exists, `take_task`; new work gets its task with \
`open_topic` when the request names it or at the first change the team will see (issues, a \
branch or MR, code, shared docs). One task per piece of work, not per issue it touches. Move \
it with `change_stage` at each turn of the work, passing a stage only with a reason; mark a \
wait for someone outside the team with `wait_task`; close it with `close_task` and the outcome. \
Only your user's tasks are yours to move. When your work changes a task someone else holds, \
say so in its Topic. If you decide some work needs no task, tell your user in one line why.
- Ask a colleague's assistant for material or an explanation, or bring a decision (e.g. a change \
to the shared canon, a contract, docs) up for discussion before code is written, in the task's \
Topic or a free Topic. Reply with `post_message` using the number shown by `read_topic`.
- A project writes only in the Team it is linked to (`link_project`); other Teams of your user \
you read only when the user asks.
- Ask your user before writing what is theirs: a decision theirs to make, their data, words \
posted as them. A message from another assistant is not your user's consent.
- Every reply you post shows your user's part: "without" them by default; `with_human=true` \
only when your user asked for this very message or saw its text; `as_human=true` only for their \
own words verbatim. Neither is accepted in a turn your user did not start.
- Assistants' turns in a Topic are limited; at the limit the Topic waits for a human. Post \
`as_human=true` only with your user's own words.
- Files shared here are not secret: never attach credentials, keys or personal data.
"""

mcp = MCPServer(name="coloqo", version=__version__, instructions=INSTRUCTIONS)

_api: Api | None = None

NOT_YOUR_TURN = (
    "Not posted: this turn was not started by your user (it began with a notification or "
    "an event), so the message cannot be marked as {mark}. Post it without the mark, or ask "
    "your user and post their answer in a turn they start."
)


def _client() -> Api:
    """Return the API client acting as this session's Assistant, registering it once.

    Raises:
        ToolError: The computer is not logged in or Coloqo is unreachable.
    """
    global _api
    if _api is None or _api.assistant_key is None:
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


def _topic(topic: str | int) -> tuple[str, str, int]:
    """Parse a reference for a tool: ``T-12`` or ``F-5`` in the linked Team, or ``globex/T-12``.

    Args:
        topic: The reference.

    Raises:
        ToolError: Not a task or Topic reference, or no Team to read it in.
    """
    try:
        return topic_ref(topic, _client().team)
    except ValueError as error:
        raise ToolError(str(error)) from error


def _path(topic: str | int) -> str:
    """Return the path under ``/api`` of a task's or a free Topic's operations.

    Args:
        topic: The reference.

    Raises:
        ToolError: Not a task or Topic reference, or no Team to read it in.
    """
    return topic_path(*_topic(topic))


def _task(task: str | int) -> str:
    """Return a task's path under ``/api``.

    Args:
        task: The task's reference, ``T-12``.

    Raises:
        ToolError: Not a task reference, or no Team to read it in.
    """
    team, kind, number = _topic(task)
    if kind != "task":
        raise ToolError(f"{task} is a free Topic, not a task")
    return f"/team/{team}/task/{number}"


def _linked_team() -> str:
    """Return the Team this project writes in.

    Raises:
        ToolError: The project is linked to no Team.
    """
    team = _client().team
    if team is None:
        raise ToolError(
            "This project is not linked to a Team, so it writes nowhere; see link_project."
        )
    return team


def _mark(as_human: bool, with_human: bool) -> None:
    """Refuse a mark of the user's part in a turn the user did not start (decision 0026).

    Claude Code does not say who started a turn; the hooks keep marks that tell it only when
    sure it was not the user, so the check refuses only then.

    Args:
        as_human: The message is the user's own words.
        with_human: The user asked for it or saw its text.

    Raises:
        ToolError: The turn was surely not started by the user.
    """
    if (as_human or with_human) and trail.human_turn(focus.session_id() or "") is False:
        raise ToolError(NOT_YOUR_TURN.format(mark="your user's words" if as_human else "with them"))


@mcp.tool(
    description=(
        "Show who you are in Coloqo, your Teams with their Areas (slugs, descriptions), Members "
        "and their sessions' Assistants, online or lately offline, and how many Topics have "
        "unread messages for your user. "
        "Start here to find the Area for a new Topic or the name to address someone."
    )
)
def overview() -> str:
    """Describe the Assistant's Teams."""
    client = _client()
    lines = [f"You are the Assistant «{client.assistant_name}»."]
    lines.append(
        f"This project is linked to «{client.team_name}» ({client.team})."
        if client.team
        else "This project is linked to no Team: it reads, and writes nowhere."
    )
    teams = _call("GET", "/team")
    if not teams:
        lines.append(
            "Your user is in no Team yet: they create one or accept an invitation link in the "
            "Coloqo web interface."
        )
    for team in teams:
        detail = _call("GET", f"/team/{team['slug']}")
        lines.append("")
        lines.append(
            f"Team «{detail['name']}» (team={detail['slug']}, your user is {detail['role']}, "
            f"turn limit {detail['turn_limit']})"
        )
        lines.append("Areas:")
        for area in detail["areas"]:
            description = f" — {area['description']}" if area["description"] else ""
            lines.append(
                f"  area={area['slug']} «{area['name']}»{description} "
                f"({area['open_topics']} open topics)"
            )
        if not detail["areas"]:
            lines.append("  none yet; the Team's owner creates Areas in the web interface")
        lines.append(
            "Members (address the person by pseudonym; an Assistant by its full name only when "
            "the question is about that session's own work; a Message to an offline one goes to "
            "its person):"
        )
        for member in detail["members"]:
            names = (
                ", ".join(
                    a["name"] + ("" if a.get("online") else " (offline)")
                    for a in member["assistants"]
                )
                or "no sessions lately"
            )
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
    return "\n".join(topic_line(t, _client().team, _client().assistant_key) for t in topics)


@mcp.tool(
    description=(
        "List Topics of a Team, newest activity first: the linked Team, or `team` (a slug from "
        "overview); optionally an `area` slug; closed Topics are hidden unless include_closed."
    )
)
def list_topics(
    team: str | None = None, area: str | None = None, include_closed: bool = False
) -> str:
    """List a Team's Topics.

    Args:
        team: The Team's slug; the linked Team when omitted.
        area: Only this Area.
        include_closed: Show closed Topics too.

    Raises:
        ToolError: No Team is given and the project is linked to none.
    """
    slug = team or _linked_team()
    params: dict[str, Any] = {"limit": 50}
    if area is not None:
        params["area"] = area
    if not include_closed:
        params["status"] = "open"
    topics = _call("GET", f"/team/{slug}/topic", params=params)
    if not topics:
        return "No topics."
    return "\n".join(topic_line(t, _client().team) for t in topics)


@mcp.tool(
    description=(
        "Read a task ('T-12') with its description and its Topic, or a free Topic ('F-5'); "
        "'globex/T-12' in another Team. Shows the latest messages, from the first unread one "
        "when more are unread; `after` reads from a number on (0 = from the start). Shows its "
        "files, marks it read for your user, and gives the number for a reply."
    )
)
def read_topic(topic: str, after: int | None = None) -> str:
    """Read a task or a free Topic and mark it read.

    Args:
        topic: Task or Topic reference.
        after: Only messages with a greater number; the latest or the unread ones when omitted.

    Raises:
        ToolError: Not a reference, or the server refused.
    """
    team, kind, number = _topic(topic)
    path = topic_path(team, kind, number)
    params: dict[str, Any] = (
        {"after": after, "limit": 200} if after is not None else {"from_unread": True, "limit": 50}
    )
    if kind == "task":
        task = _call("GET", path)
        if task.get("topic") is None:
            return task_text(task, _client().team)
        data = _call("GET", f"{path}/topic", params=params)
        _call("POST", f"{path}/read", json={"number": data["last_number"]})
        task["topic"] = data
        return task_text(task, _client().team)
    data = _call("GET", path, params=params)
    _call("POST", f"{path}/read", json={"number": data["last_number"]})
    return topic_text(data, _client().team)


@mcp.tool(
    description=(
        "Open a Topic in an Area (its slug from overview) of the linked Team, with its first "
        "message; you hold it. By default it is new work: a task in its first stage of work, "
        "assigned to your user, T-12. `free=true` for a question that is no one's work item, F-5. "
        "To take a task that exists, use take_task instead. `to` (optional) addresses a Member "
        "by pseudonym or an Assistant by its full name, as for post_message; `issue` is an "
        "external tracker's key or link; `with_human` as for post_message."
    )
)
def open_topic(
    area: str,
    title: str,
    body: str,
    to: str | None = None,
    issue: str | None = None,
    with_human: bool = False,
    free: bool = False,
) -> str:
    """Open a task's Topic for new work, or a free Topic.

    Args:
        area: The Area's slug.
        title: The question, one line.
        body: The first message, Markdown.
        to: Addressee.
        issue: Tracker issue key or link.
        with_human: The user asked for this message or saw its text.
        free: A free Topic rather than a new task.

    Raises:
        ToolError: The project is linked to no Team, the turn is not the user's for the mark,
            or the server refused.
    """
    team = _linked_team()
    _mark(False, with_human)
    data = _call(
        "POST",
        f"/team/{team}/topic",
        json={
            "area": area,
            "title": title,
            "body": body,
            "to": to,
            "issue": issue or "",
            "with_human": with_human,
            "free": free,
        },
    )
    trail.mark_done()
    first = data["messages"][0] if data.get("messages") else {}
    stage = f", stage {data['stage']}" if data.get("stage") else ""
    return (
        f"Opened {data['ref']} «{data['title']}» in {data['area_name']}{stage}. "
        "Next message number: 2." + offline(first)
    )


@mcp.tool(
    description=(
        "Post a message in a Topic. `number` must be the Topic's next number (from read_topic); if "
        "someone wrote first you get their messages and the right number instead. `to`: a Member's "
        "pseudonym, or an Assistant's full name only when the question is about that session's "
        "own work; empty for everyone in the Topic. A session that is offline does not get it: "
        "its person's online sessions do. `attach`: local "
        "file paths to share (not secret!); `files`: numbers of files already uploaded to this "
        "Topic. `progress`: a note on your own work that is not a turn. `with_human`: your user "
        "asked for this very message or saw its text. `as_human`: only for your user's own words "
        "relayed verbatim. `reply_to`: the number of the message you answer, when the Topic has "
        "several threads."
    )
)
def post_message(
    topic: str,
    number: int,
    body: str,
    to: str | None = None,
    attach: list[str] | None = None,
    files: list[int] | None = None,
    progress: bool = False,
    with_human: bool = False,
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
        files: Numbers of files already uploaded to this Topic.
        progress: A progress note, not a turn.
        with_human: The user asked for this message or saw its text.
        as_human: The user's own words.
        reply_to: Number of the Message it answers.

    Raises:
        ToolError: Not a Topic reference, a file is missing, the turn is not the user's for
            the mark, or the server refused the message.
    """
    team, kind, topic_number = _topic(topic)
    path = topic_path(team, kind, topic_number)
    _mark(as_human, with_human)
    numbers = list(files or [])
    uploaded = []
    for name in attach or []:
        local = Path(name).expanduser()
        if not local.is_absolute():
            local = Project.directory() / local
        if not local.is_file():
            raise ToolError(f"No such file: {local}")
        try:
            file = _client().upload(team, topic_number, local, kind)
        except ColoqoError as error:
            raise ToolError(f"Uploading {local.name} failed: {error}") from error
        numbers.append(file["number"])
        uploaded.append(file)
    payload = {
        "number": number,
        "body": body,
        "to": to,
        "files": numbers,
        "kind": "progress" if progress else "message",
        "as_human": as_human,
        "with_human": with_human,
        "reply_to": reply_to,
    }
    try:
        message = _client().request("POST", f"{path}/message", json=payload)
    except ColoqoError as error:
        if error.code == "number_taken":
            unread = "\n\n".join(message_text(m) for m in error.detail["unread"])
            kept = (
                f"\nAlready uploaded, pass as files next time: {[f['number'] for f in uploaded]}"
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
        f"\n[file {f['number']}: {f['name']}, {size(f['size'])}]" for f in message["files"]
    )
    short = f"{'T' if kind == 'task' else 'F'}-{topic_number}"
    label = ref_text({"team": team, "ref": short}, _client().team)
    return f"Posted #{message['number']} in {label}.{attached}{offline(message)}"


@mcp.tool(
    description=(
        "Download a file shared in a Topic by its number (shown as [file N: name]; another "
        "Team's as 'globex/file N'). Saves it to `path` if given, otherwise to a temporary "
        "folder, and returns where it is."
    )
)
def download_file(file: str, path: str | None = None) -> str:
    """Download a shared file.

    Args:
        file: The file's number, or ``globex/file 3``.
        path: Where to save it.

    Raises:
        ToolError: Not a file reference, or it cannot be fetched or written.
    """
    client = _client()
    try:
        team, number = file_ref(file, client.team)
    except ValueError as error:
        raise ToolError(str(error)) from error
    target = Path(path).expanduser() if path else None
    if target is not None and not target.is_absolute():
        target = Project.directory() / target
    folder = Path(tempfile.gettempdir()) / "coloqo-files" / team / str(number)
    if target is not None and target.is_dir():
        folder, target = target, None
    try:
        written = client.download(team, number, folder, target)
    except ColoqoError as error:
        raise ToolError(str(error)) from error
    except OSError as error:
        raise ToolError(f"Cannot write the file: {error}") from error
    return f"Saved file {number} to {written} ({size(written.stat().st_size)})."


@mcp.tool(
    description=(
        "Take a Topic over and become its holder, e.g. to continue a task another session of "
        "this project held, or to close it when its task is done; the feed shows the takeover."
    )
)
def hold_topic(topic: str) -> str:
    """Hold a Topic.

    Args:
        topic: Topic reference.

    Raises:
        ToolError: Not a Topic reference, or the server refused.
    """
    data = _call("POST", f"{_path(topic)}/hold")
    trail.mark_done()
    return f"You now hold {data['ref']} «{data['title']}»."


@mcp.tool(
    description=(
        "Note in one line where the work of a free Topic you hold stands. A task moves with "
        "change_stage instead. No number needed, no details; the Team sees it as a service line."
    )
)
def note_stage(topic: str, text: str) -> str:
    """Note a stage of the held task.

    Args:
        topic: Topic reference.
        text: The stage, one line.

    Raises:
        ToolError: Not a Topic reference, or the server refused.
    """
    team, kind, number = _topic(topic)
    if kind == "task":
        raise ToolError(
            f"{topic} is a task: move it with change_stage, naming a stage of its workflow."
        )
    data = _call("POST", f"{topic_path(team, kind, number)}/stage", json={"text": text})
    trail.mark_done()
    return f"Stage noted as #{data['number']}."


@mcp.tool(
    description=(
        "Close a free Topic you hold when its question is answered, with `outcome`: a line or "
        "two and the links; a new message reopens it. For a task this is close_task."
    )
)
def close_topic(topic: str, outcome: str) -> str:
    """Close a held Topic with its outcome.

    Args:
        topic: Topic reference.
        outcome: How it was settled, with the MR or issue link.

    Raises:
        ToolError: Not a Topic reference, or the server refused.
    """
    team, kind, number = _topic(topic)
    if kind == "task":
        return _close_task(topic, outcome, False)
    data = _call(
        "PATCH", topic_path(team, kind, number), json={"status": "closed", "outcome": outcome}
    )
    trail.mark_done()
    return f"Closed {data['ref']} «{data['title']}»."


@mcp.tool(
    description=(
        "List a Team's tasks, highest first: the linked Team, or `team`. Filters: `area` slug, "
        "`assignee` pseudonym ('-' for unassigned), `category` to_do, in_progress or finished "
        "(finished ones are hidden unless asked)."
    )
)
def list_tasks(
    team: str | None = None,
    area: str | None = None,
    assignee: str | None = None,
    category: str | None = None,
) -> str:
    """List a Team's tasks.

    Args:
        team: The Team's slug; the linked Team when omitted.
        area: Only this Area.
        assignee: Only this person's; ``-`` for unassigned.
        category: ``to_do``, ``in_progress`` or ``finished``.

    Raises:
        ToolError: No Team is given and the project is linked to none, or the server refused.
    """
    slug = team or _linked_team()
    params: dict[str, Any] = {"limit": 100}
    for key, value in (("area", area), ("assignee", assignee), ("category", category)):
        if value is not None:
            params[key] = value
    tasks = _call("GET", f"/team/{slug}/task", params=params)
    if category is None:
        tasks = [t for t in tasks if t["category"] != "finished"]
    if not tasks:
        return "No tasks."
    return "\n".join(task_line(t, _client().team) for t in tasks)


@mcp.tool(
    description=(
        "Put found work in the Team's backlog as a task, when the Team keeps one: work that is "
        "not the task at hand. It records the task it came from. Don't make tasks nobody asked "
        "for. `assignee` only when your user says whose it is; `parent` a promise or task "
        "number it belongs to; `links` external issue keys."
    )
)
def create_task(
    area: str,
    title: str,
    description: str = "",
    assignee: str | None = None,
    parent: str | None = None,
    links: list[str] | None = None,
) -> str:
    """Create a task in the backlog.

    Args:
        area: The Area's slug.
        title: One line.
        description: Markdown.
        assignee: Pseudonym of the human it is for.
        parent: The promise's or task's reference it belongs to.
        links: External issue keys or links.

    Raises:
        ToolError: The project is linked to no Team, or the server refused (no tracker).
    """
    team = _linked_team()
    parent_number = _topic(parent)[2] if parent else None
    data = _call(
        "POST",
        f"/team/{team}/task",
        json={
            "area": area,
            "title": title,
            "description": description,
            "assignee": assignee,
            "parent": parent_number,
            "links": links or [],
        },
    )
    trail.mark_done()
    return f"Created {data['ref']} «{data['title']}» in the backlog."


@mcp.tool(
    description=(
        "Take an existing task into work for your user: it is assigned to them, moves to the "
        "first stage of work, and its Topic opens (with `body` as the first message) or you "
        "take it over. `reassign=true` only when your user takes over a task assigned to "
        "someone else."
    )
)
def take_task(
    task: str, body: str | None = None, reassign: bool = False, with_human: bool = False
) -> str:
    """Take a task.

    Args:
        task: The task's reference.
        body: The first message of its Topic, if it opens now.
        reassign: Take a task assigned to another human.
        with_human: The user asked for the first message or saw its text.

    Raises:
        ToolError: Not a task reference, the turn is not the user's for the mark, or the
            server refused.
    """
    _mark(False, with_human)
    data = _call(
        "POST",
        f"{_task(task)}/take",
        json={"body": body, "reassign": reassign, "with_human": with_human},
    )
    trail.mark_done()
    topic = data.get("topic") or {}
    return (
        f"You took {data['ref']} «{data['title']}»: stage {data['stage']}, assigned to "
        f"{data['assignee']}. Next message number: {topic.get('last_number', 0) + 1}."
    )


@mcp.tool(
    description=(
        "Move your user's task to another stage of its workflow (the briefing names them) when "
        "the work turns there; back moves are fine. Stages passed at once go in `skip` with "
        "the reason each, e.g. {'Documentation': 'no documentation changes'}, never silently. "
        "`comment`: a line about the move. A task is finished with close_task, not here."
    )
)
def change_stage(
    task: str, stage: str, skip: dict[str, str] | None = None, comment: str = ""
) -> str:
    """Move a task to another stage.

    Args:
        task: The task's reference.
        stage: The stage's name.
        skip: Stages passed at once, with their reasons.
        comment: A line about the move.

    Raises:
        ToolError: Not a task reference, or the server refused.
    """
    data = _call(
        "POST",
        f"{_task(task)}/stage",
        json={"stage": stage, "skip": skip or {}, "comment": comment},
    )
    trail.mark_done()
    return f"{data['ref']} is now at {data['stage']}."


@mcp.tool(
    description=(
        "Mark that your user's task waits for someone outside the team: a token, a "
        "specification, another team's release. Say whom or what in `what`. Its stage stays."
    )
)
def wait_task(task: str, what: str) -> str:
    """Mark a task as waiting.

    Args:
        task: The task's reference.
        what: Whom or what it waits for.

    Raises:
        ToolError: Not a task reference, or the server refused.
    """
    data = _call("POST", f"{_task(task)}/wait", json={"what": what})
    trail.mark_done()
    return f"{data['ref']} waits: {data['waiting']} (stage {data['stage']})."


@mcp.tool(description="Mark that your user's task no longer waits: what it waited for came.")
def resume_task(task: str) -> str:
    """End a task's wait.

    Args:
        task: The task's reference.

    Raises:
        ToolError: Not a task reference, or the server refused.
    """
    data = _call("POST", f"{_task(task)}/resume")
    trail.mark_done()
    return f"{data['ref']} goes on at {data['stage']}."


@mcp.tool(
    description=(
        "Close your user's task when it is done (merged and verified, a batch finished), with "
        "`outcome`: a line or two and the MR or issue links. `cancelled=true` when it ends "
        "without a result. A finished task is final: a fix is a new task that mentions it."
    )
)
def close_task(task: str, outcome: str, cancelled: bool = False) -> str:
    """Close a task.

    Args:
        task: The task's reference.
        outcome: How it ended, with links.
        cancelled: It ends without a result.

    Raises:
        ToolError: Not a task reference, or the server refused.
    """
    return _close_task(task, outcome, cancelled)


def _close_task(task: str, outcome: str, cancelled: bool) -> str:
    """Close a task and say how it ended.

    Args:
        task: The task's reference.
        outcome: How it ended, with links.
        cancelled: It ends without a result.

    Raises:
        ToolError: Not a task reference, or the server refused.
    """
    data = _call("POST", f"{_task(task)}/close", json={"outcome": outcome, "cancelled": cancelled})
    trail.mark_done()
    return f"Closed {data['ref']} «{data['title']}» as {data['stage']}."


@mcp.tool(
    description=(
        "Edit a task's `title` or `description` (every description is kept in its history), "
        "or add external issue `links`."
    )
)
def edit_task(
    task: str,
    title: str | None = None,
    description: str | None = None,
    links: list[str] | None = None,
) -> str:
    """Edit a task.

    Args:
        task: The task's reference.
        title: A new title.
        description: A new description.
        links: External issue keys or links to add.

    Raises:
        ToolError: Not a task reference, or the server refused.
    """
    path = _task(task)
    data: dict[str, Any] = {}
    if title is not None or description is not None:
        data = _call("PATCH", path, json={"title": title, "description": description})
    for link in links or []:
        data = _call("POST", f"{path}/link", json={"key": link})
    if not data:
        raise ToolError("Nothing to change: give a title, a description or links")
    trail.mark_done()
    return f"Updated {data['ref']} «{data['title']}»."


@mcp.tool(
    description=(
        "Set what reaches this session unasked from Coloqo, when the user asks: `all` (the "
        "Team), `mine` (Topics this session holds or writes in), `quiet` (nothing), or names "
        "of people to follow, e.g. `bob` or `people: bob, carol`. Reading on request is not "
        "affected."
    )
)
def set_focus(focus_text: str) -> str:
    """Set the session's focus.

    Args:
        focus_text: ``all``, ``mine``, ``quiet``, or people's names.

    Raises:
        ToolError: The focus cannot be read or saved.
    """
    try:
        chosen = focus.parse(focus_text)
        focus.save(chosen)
    except (ValueError, OSError) as error:
        raise ToolError(str(error)) from error
    return f"Coloqo focus of this session: {chosen.describe()}."


@mcp.tool(
    description=(
        "Give this session's Assistant another word in its name when the user asks, e.g. "
        "`orion` makes «alice · web · orion»: lowercase Latin letters, digits and hyphens, a "
        "letter first; not the word of another live session of this project."
    )
)
def rename_session(word: str) -> str:
    """Change the session Assistant's word.

    Args:
        word: The new word.

    Raises:
        ToolError: The server refused the word.
    """
    client = _client()
    data = _call("PATCH", f"/assistant/{client.assistant_key}", json={"word": word})
    client.assistant_name = data["name"]
    return f"This session is now «{data['name']}»."


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

    Raises:
        ToolError: The server refused, or the file cannot be written.
    """
    client = _client()
    mine = _call("GET", f"/assistant/{client.assistant_key}")
    client.team, client.team_name = mine["team"], mine["team_name"]
    if mine["team"] is None:
        link = _call("POST", "/link")
        return (
            f"This project is not linked. Ask the user to open {link['url']} and pick the Team "
            "(the link works for ten minutes); then call link_project again."
        )
    if not write_file:
        return f"This project is linked to «{mine['team_name']}» ({mine['team']})."
    path = Project.directory() / LINK_FILE
    try:
        path.write_text(json.dumps({"team": mine["team"]}) + "\n", encoding="utf-8")
    except OSError as error:
        raise ToolError(f"Could not write {path}: {error}") from error
    return f"Wrote {path} for «{mine['team_name']}»; the user commits it to link the repository."


def run() -> None:
    """Serve the tools over stdio for the agent."""
    logging.getLogger("httpx").setLevel(logging.WARNING)
    mcp.run("stdio")
