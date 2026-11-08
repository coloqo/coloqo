"""Plain-text views of Coloqo data for the model and for the terminal."""

import re
from typing import Any

TOPIC_LINK = re.compile(r"/team/([a-z0-9-]+)/(topic|task)/(\d+)")
"""A task's or a free Topic's address in the web or the API (decisions 0025, 0031)."""


def _split(value: str | int, home: str | None) -> tuple[str, str]:
    """Split a reference into its Team and the rest: ``globex/T-12`` or ``T-12`` at home.

    Args:
        value: The reference.
        home: The Team the project is linked to, for a reference without a Team.

    Raises:
        ValueError: No Team is named and the project is linked to none.
    """
    text = str(value).strip()
    team, slash, rest = text.rpartition("/")
    if slash:
        return team.strip().lower(), rest.strip()
    if home is None:
        raise ValueError(
            f"{value!r} names no Team, and this project is linked to none: write team/T-12"
        )
    return home, text


def topic_ref(value: str | int, home: str | None) -> tuple[str, str, int]:
    """Return a Topic's Team, kind and number from ``T-12``, ``F-5``, ``12``, ``globex/T-12`` or
    a link.

    ``T-12`` (or a bare number) is the task 12 and its Topic; ``F-5`` the free Topic 5
    (decision 0031).

    Args:
        value: A task or Topic reference.
        home: The Team the project is linked to, meant when the reference names none.

    Raises:
        ValueError: The value names no task or Topic.
    """
    found = TOPIC_LINK.search(str(value))
    if found:
        kind = "task" if found.group(2) == "task" else "free"
        return found.group(1), kind, int(found.group(3))
    team, rest = _split(value, home)
    text = rest.upper().strip()
    kind = "free" if text.startswith("F") else "task"
    number = text.removeprefix("T").removeprefix("F").removeprefix("-").strip()
    if not number.isdigit():
        raise ValueError(f"{value!r} is not a reference like T-12, F-5 or globex/T-12")
    return team, kind, int(number)


def topic_path(team: str, kind: str, number: int) -> str:
    """Return the address under ``/api`` of a task's or a free Topic's operations.

    Args:
        team: The Team's slug.
        kind: ``task`` or ``free``.
        number: The task's or the free Topic's number.
    """
    return f"/team/{team}/{'task' if kind == 'task' else 'topic'}/{number}"


def file_ref(value: str | int, home: str | None) -> tuple[str, int]:
    """Return a file's Team and number from ``3``, ``file 3`` or ``globex/file 3``.

    Args:
        value: A file reference.
        home: The Team the project is linked to, meant when the reference names none.

    Raises:
        ValueError: The value names no file.
    """
    team, rest = _split(value, home)
    number = rest.lower().removeprefix("file").strip()
    if not number.isdigit():
        raise ValueError(f"{value!r} is not a file reference like 3 or globex/file 3")
    return team, int(number)


def ref_text(topic: dict[str, Any], home: str | None) -> str:
    """Return how to name a Topic from a project linked to ``home``.

    Args:
        topic: A Topic from the API.
        home: The Team the project is linked to.
    """
    return topic["ref"] if topic.get("team") == home else f"{topic.get('team')}/{topic['ref']}"


def size(n: int) -> str:
    """Return a byte count for people.

    Args:
        n: Bytes.
    """
    if n < 1024:
        return f"{n} B"
    value = n / 1024
    for unit in ("KB", "MB"):
        if value < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def topic_line(topic: dict[str, Any], home: str | None = None, me: str | None = None) -> str:
    """Return one line about a Topic.

    Args:
        topic: A Topic from the API.
        home: The Team the project is linked to; another Team's Topic shows its slug.
        me: This session's Assistant key, to tell a message addressed to another session of
            the user (decision 0029).
    """
    parts = [
        f"{ref_text(topic, home)} «{topic['title']}»",
        f"Area: {topic.get('area_name') or topic['area']}",
    ]
    if topic.get("stage"):
        parts.append(f"stage {topic['stage']}")
    if topic.get("assignee"):
        parts.append(f"assigned to {topic['assignee']}")
    if topic.get("waiting"):
        parts.append(f"waiting: {topic['waiting']}")
    if topic["status"] != "open":
        parts.append(topic["status"])
    if topic.get("holder"):
        parts.append(f"held by {topic['holder']}")
    parts.append(f"{topic['last_number']} messages")
    if topic.get("unread"):
        marker = ""
        if topic.get("addressed"):
            via = topic.get("addressed_via_key")
            marker = (
                f", addressed to your user through {topic.get('addressed_via')}, another "
                "session, which answers it"
                if via and via != me
                else ", addressed to you"
            )
        parts.append(f"{topic['unread']} unread{marker}")
    return " · ".join(parts)


def _author(message: dict[str, Any]) -> str:
    """Return who wrote a Message.

    Args:
        message: A Message from the API.
    """
    return message["assistant"] or f"{message['author']} (human)"


def offline(message: dict[str, Any]) -> str:
    """Return what the sender learns when a Message meant for an offline session went to its
    person instead (decision 0029), or nothing.

    Args:
        message: A Message from the API.
    """
    if not message.get("meant_for"):
        return ""
    return (
        f"\n{message['meant_for']} is offline, so the message went to {message['to']}: their "
        "online sessions see it, and their Inbox keeps it."
    )


HUMAN_PART = {
    "without": "[without {person}]",
    "with": "[with {person}]",
    "words": "[{person}'s words]",
}
"""How the human's part in an Assistant's reply reads (decision 0026)."""


def message_text(message: dict[str, Any]) -> str:
    """Return a Message as a block of text.

    Args:
        message: A Message from the API.
    """
    head = f"#{message['number']} {_author(message)}"
    if message.get("reply_to"):
        head += f" ↪ #{message['reply_to']}"
    if message.get("to_assistant"):
        head += f" → {message['to_assistant']}"
    elif message.get("to"):
        head += f" → {message['to']}"
        if message.get("meant_for"):
            head += f" (meant for {message['meant_for']}, which was offline)"
    part = message.get("human_part")
    if part in HUMAN_PART:
        head += " " + HUMAN_PART[part].format(person=message["author"])
    if message["kind"] == "progress":
        head += " [progress]"
    elif message["kind"] == "stage":
        head += " [stage]"
    elif message["kind"] == "closed":
        head += " [closed with the outcome]"
    elif message["kind"] == "taken":
        head += f" [took the Topic over from {message['body'] or 'nobody'}]"
    head += f" · {message['created_at'][:16].replace('T', ' ')}"
    # A takeover's body is the former holder, already named in the head.
    lines = [head] if message["kind"] == "taken" else [head, message["body"]]
    for file in message.get("files", []):
        lines.append(f"[file {file['number']}: {file['name']}, {size(file['size'])}]")
    return "\n".join(lines)


def topic_text(topic: dict[str, Any], home: str | None = None) -> str:
    """Return a Topic with its Messages, and how to reply.

    Args:
        topic: A Topic with ``messages`` and ``files`` from the API.
        home: The Team the project is linked to; another Team's Topic shows its slug.
    """
    lines = [
        f"{ref_text(topic, home)} «{topic['title']}» — Area: "
        f"{topic.get('area_name') or topic['area']}, {topic['status']}",
    ]
    if topic.get("stage"):
        lines.append(
            f"Task stage: {topic['stage']}"
            + (f", assigned to {topic['assignee']}" if topic.get("assignee") else "")
            + (f", waiting: {topic['waiting']}" if topic.get("waiting") else "")
        )
    if topic.get("issue"):
        lines.append(f"Issue: {topic['issue']}")
    if topic.get("holder"):
        lines.append(f"Held by: {topic['holder']}")
    if topic.get("outcome"):
        lines.append(f"Outcome: {topic['outcome']}")
    lines.append(
        f"Assistants' turns without a human: {topic['turns_since_human']}/{topic['turn_limit']}"
    )
    lines.append("")
    if topic["messages"] and topic["messages"][0]["number"] > 1:
        lines.append(
            f"(earlier messages: read_topic with after=0 starts from #1; these start at "
            f"#{topic['messages'][0]['number']})"
        )
        lines.append("")
    for message in topic["messages"]:
        lines.append(message_text(message))
        lines.append("")
    if not topic["messages"]:
        lines.append("(no new messages)")
        lines.append("")
    unattached = [f for f in topic.get("files", []) if f.get("message_number") is None]
    if unattached:
        lines.append(
            "Files not attached to a message: "
            + ", ".join(f"[file {f['number']}: {f['name']}]" for f in unattached)
        )
    lines.append(f"To reply, post with number={topic['last_number'] + 1}.")
    return "\n".join(lines)


def task_line(task: dict[str, Any], home: str | None = None) -> str:
    """Return one line about a task.

    Args:
        task: A task from the API.
        home: The Team the project is linked to; another Team's task shows its slug.
    """
    parts = [
        f"{ref_text(task, home)} «{task['title']}»",
        f"{task['type']}" if task.get("type") == "promise" else None,
        f"Area: {task.get('area_name') or task['area']}",
        f"stage {task['stage']}",
        f"assigned to {task['assignee']}" if task.get("assignee") else "unassigned",
        f"waiting: {task['waiting']}" if task.get("waiting") else None,
        f"in T-{task['parent']}" if task.get("parent") else None,
    ]
    return " · ".join(part for part in parts if part)


def task_text(task: dict[str, Any], home: str | None = None) -> str:
    """Return a task with its description and links, and its Topic if it has one.

    Args:
        task: A task with ``description`` and ``topic`` from the API.
        home: The Team the project is linked to.
    """
    lines = [task_line(task, home)]
    if task.get("links"):
        lines.append("Links: " + ", ".join(link["url"] or link["key"] for link in task["links"]))
    if task.get("source"):
        lines.append(f"Found within T-{task['source']}")
    if task.get("outcome"):
        lines.append(f"Outcome: {task['outcome']}")
    lines.append("")
    lines.append(task.get("description") or "(no description)")
    lines.append("")
    if task.get("topic"):
        lines.append(topic_text(task["topic"], home))
    else:
        lines.append("No Topic yet: take_task opens it.")
    return "\n".join(lines)
