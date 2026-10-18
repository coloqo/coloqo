"""Plain-text views of Coloqo data for the model and for the terminal."""

from typing import Any


def topic_ref(value: str | int) -> int:
    """Return a Topic id from ``T-12``, ``t12``, ``12`` or ``12``.

    Args:
        value: A Topic reference.

    Raises:
        ValueError: The value names no Topic.
    """
    text = str(value).strip().upper().removeprefix("T").removeprefix("-").strip()
    if not text.isdigit():
        raise ValueError(f"{value!r} is not a Topic reference like T-12")
    return int(text)


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


def topic_line(topic: dict[str, Any]) -> str:
    """Return one line about a Topic.

    Args:
        topic: A Topic from the API.
    """
    parts = [f"{topic['ref']} «{topic['title']}»", f"Area: {topic['area']}"]
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


def message_text(message: dict[str, Any]) -> str:
    """Return a Message as a block of text.

    Args:
        message: A Message from the API.
    """
    head = f"#{message['number']} {_author(message)}"
    if message.get("to_assistant"):
        head += f" → {message['to_assistant']}"
    elif message.get("to"):
        head += f" → {message['to']}"
    if message.get("relayed"):
        head += " [the human's own words]"
    if message["kind"] == "progress":
        head += " [progress]"
    head += f" · {message['created_at'][:16].replace('T', ' ')}"
    lines = [head, message["body"]]
    for file in message.get("files", []):
        lines.append(f"[file {file['id']}: {file['name']}, {size(file['size'])}]")
    return "\n".join(lines)


def topic_text(topic: dict[str, Any]) -> str:
    """Return a Topic with its Messages, and how to reply.

    Args:
        topic: A Topic with ``messages`` and ``files`` from the API.
    """
    lines = [
        f"{topic['ref']} «{topic['title']}» — Area: {topic['area']}, {topic['status']}",
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
            + ", ".join(f"[file {f['id']}: {f['name']}]" for f in unattached)
        )
    lines.append(f"To reply, post with number={topic['last_number'] + 1}.")
    return "\n".join(lines)
