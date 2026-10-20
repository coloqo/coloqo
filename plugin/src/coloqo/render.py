"""Plain-text views of Coloqo data for the model and for the terminal."""

import re
from typing import Any

TOPIC_LINK = re.compile(r"/team/([a-z0-9-]+)/topic/(\d+)")
"""A Topic's address in the web or the API (decision 0025)."""


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


def topic_ref(value: str | int, home: str | None) -> tuple[str, int]:
    """Return a Topic's Team and number from ``T-12``, ``12``, ``globex/T-12`` or its link.

    Args:
        value: A Topic reference.
        home: The Team the project is linked to, meant when the reference names none.

    Raises:
        ValueError: The value names no Topic.
    """
    found = TOPIC_LINK.search(str(value))
    if found:
        return found.group(1), int(found.group(2))
    team, rest = _split(value, home)
    number = rest.upper().removeprefix("T").removeprefix("-").strip()
    if not number.isdigit():
        raise ValueError(f"{value!r} is not a Topic reference like T-12 or globex/T-12")
    return team, int(number)


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


def topic_line(topic: dict[str, Any], home: str | None = None) -> str:
    """Return one line about a Topic.

    Args:
        topic: A Topic from the API.
        home: The Team the project is linked to; another Team's Topic shows its slug.
    """
    parts = [
        f"{ref_text(topic, home)} «{topic['title']}»",
        f"Area: {topic.get('area_name') or topic['area']}",
    ]
    if topic["status"] != "open":
        parts.append(topic["status"])
    if topic.get("holder"):
        parts.append(f"held by {topic['holder']}")
    parts.append(f"{topic['last_number']} messages")
    if topic.get("unread"):
        marker = ", addressed to you" if topic.get("addressed") else ""
        parts.append(f"{topic['unread']} unread{marker}")
    return " · ".join(parts)


def _author(message: dict[str, Any]) -> str:
    """Return who wrote a Message.

    Args:
        message: A Message from the API.
    """
    return message["assistant"] or f"{message['author']} (human)"


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
    lines = [head, message["body"]]
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
