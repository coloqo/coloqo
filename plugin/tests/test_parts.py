"""Tests of the plugin's parts that do not need a server."""

import stat
import sys
from pathlib import Path
from typing import Any

import pytest

from coloqo import config, mcp_server
from coloqo.api import Project, _file_name
from coloqo.render import size, topic_ref, topic_text
from coloqo.watch import describe, frames

ME, MY_ASSISTANT, OTHER = 1, 10, 20


@pytest.mark.parametrize("value", ["T-12", "t12", "12", " T-12 ", 12])
def test_topic_ref_accepts_common_forms(value: str | int) -> None:
    """A Topic is named by ``T-12`` in any case, or by its number.

    Args:
        value: A reference.
    """
    assert topic_ref(value) == 12


def test_topic_ref_refuses_other_text() -> None:
    """A reference that is not a Topic raises ``ValueError``."""
    with pytest.raises(ValueError):
        topic_ref("Q-3")


def test_size() -> None:
    """Byte counts read naturally."""
    assert [size(5), size(2048), size(3 * 1024 * 1024)] == ["5 B", "2.0 KB", "3.0 MB"]


def test_frames_parses_server_sent_events() -> None:
    """Frames are split by blank lines; heartbeats have no id."""
    lines = iter(
        [
            "retry: 3000",
            "",
            "event: ready",
            'data: {"last": 4}',
            "",
            "id: 5",
            "event: message",
            'data: {"number": 2}',
            "",
        ]
    )

    assert list(frames(lines)) == [(None, "ready", {"last": 4}), ("5", "message", {"number": 2})]


def _message(**data: object) -> dict:
    """Return a message event's data with defaults.

    Args:
        **data: Fields to override.
    """
    base = {
        "ref": "T-3",
        "title": "Rename",
        "number": 4,
        "author": "bob",
        "assistant": "bob · web",
        "author_assistant_id": OTHER,
        "to_user_id": None,
        "to_assistant_id": None,
        "assistant_ids": [],
    }
    return {**base, **data}


def test_watch_reports_messages_to_me() -> None:
    """A Message addressed to the user or to this Assistant is reported."""
    to_user = describe("message", _message(to_user_id=ME), ME, MY_ASSISTANT)
    to_assistant = describe(
        "message", _message(to_user_id=ME, to_assistant_id=MY_ASSISTANT), ME, MY_ASSISTANT
    )

    assert to_user is not None and "to you" in to_user and "after=3" in to_user
    assert to_assistant is not None and "to you" in to_assistant


def test_watch_reports_topics_i_take_part_in() -> None:
    """A Message for everyone in a Topic this Assistant holds or wrote in is reported."""
    line = describe("message", _message(assistant_ids=[MY_ASSISTANT, OTHER]), ME, MY_ASSISTANT)

    assert line is not None and "to you" not in line


def test_watch_ignores_the_rest() -> None:
    """Own Messages, Messages to someone else and unrelated Topics are not reported."""
    own = _message(author_assistant_id=MY_ASSISTANT, to_user_id=ME)
    to_other = _message(assistant_ids=[MY_ASSISTANT], to_user_id=99)
    to_my_other_assistant = _message(to_user_id=ME, to_assistant_id=OTHER + 1)
    unrelated = _message()
    opening = _message(number=1, to_user_id=ME)

    for data in (own, to_other, to_my_other_assistant, unrelated, opening):
        assert describe("message", data, ME, MY_ASSISTANT) is None


def test_watch_reports_new_topics_except_own() -> None:
    """New Topics are reported, addressed ones as such; not the Assistant's own."""
    topic = {"ref": "T-3", "title": "Rename", "area": "Canon", "author": "bob"}

    assert "new topic" in describe(
        "topic", {**topic, "author_assistant_id": OTHER}, ME, MY_ASSISTANT
    )
    assert "addressed to you" in describe(
        "topic", {**topic, "author_assistant_id": OTHER, "to_user_id": ME}, ME, MY_ASSISTANT
    )
    assert (
        describe("topic", {**topic, "author_assistant_id": MY_ASSISTANT}, ME, MY_ASSISTANT) is None
    )


def test_project_key_hides_the_path(tmp_path: Path) -> None:
    """The project is sent as a hash of its path and its folder name.

    Args:
        tmp_path: Temporary directory from pytest.
    """
    project = Project.detect(str(tmp_path / "billing-api"))

    assert project.name == "billing-api"
    assert len(project.key) == 64 and str(tmp_path) not in project.key


def test_token_is_saved_per_server_and_private(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tokens are kept per server address in a file only the user can read.

    Args:
        tmp_path: Temporary directory from pytest.
        monkeypatch: Patching helper from pytest.
    """
    monkeypatch.setattr(config, "config_dir", lambda: tmp_path)

    path = config.save_token("t1", "alice", "https://a.example")
    config.save_token("t2", "alice", "https://b.example")

    assert config.load_token("https://a.example") == "t1"
    assert config.load_token("https://b.example") == "t2"
    if sys.platform != "win32":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert config.forget_token("https://a.example") is True
    assert config.load_token("https://a.example") is None


@pytest.mark.parametrize(
    ("header", "name"),
    [
        ('attachment; filename="migrate.sql"', "migrate.sql"),
        ("attachment; filename*=utf-8''%D0%BE%D1%82%D1%87%D1%91%D1%82.txt", "отчёт.txt"),
        ('attachment; filename="../../etc/passwd"', "passwd"),
        ("attachment", None),
    ],
)
def test_file_name_from_header_is_safe(header: str, name: str | None) -> None:
    """The downloaded file keeps its name but never a path.

    Args:
        header: ``Content-Disposition``.
        name: Expected file name.
    """
    assert _file_name(header) == name


def test_topic_text_says_how_to_reply() -> None:
    """A read Topic ends with the number for the reply."""
    text = topic_text(
        {
            "ref": "T-3",
            "title": "Rename",
            "area": "Canon",
            "status": "open",
            "issue": "ACME-42",
            "holder": "alice · api",
            "outcome": "",
            "turns_since_human": 1,
            "turn_limit": 10,
            "last_number": 2,
            "files": [],
            "messages": [
                {
                    "number": 1,
                    "kind": "message",
                    "author": "alice",
                    "assistant": None,
                    "to": "bob",
                    "to_assistant": None,
                    "body": "Can we?",
                    "files": [],
                    "created_at": "2026-10-19T08:00:00+00:00",
                },
                {
                    "number": 2,
                    "kind": "message",
                    "author": "bob",
                    "assistant": "bob · web",
                    "to": None,
                    "to_assistant": None,
                    "reply_to": 1,
                    "body": "Yes.",
                    "files": [],
                    "created_at": "2026-10-19T08:05:00+00:00",
                },
            ],
        }
    )

    assert "#1 alice (human) → bob" in text
    assert "#2 bob · web ↪ #1" in text
    assert text.endswith("To reply, post with number=3.")


class RecordingApi:
    """Stands in for the server: records what a tool sends and answers like it.

    Attributes:
        sent: ``(method, path, json)`` of every request.
    """

    def __init__(self) -> None:
        """Start with nothing sent."""
        self.sent: list[tuple[str, str, Any]] = []

    def request(self, method: str, path: str, json: Any = None) -> dict[str, Any]:
        """Record a request and answer with a posted Message.

        Args:
            method: HTTP method.
            path: API path.
            json: Request body.
        """
        self.sent.append((method, path, json))
        return {"number": json["number"], "files": []}


def test_post_message_sends_the_reply(monkeypatch: pytest.MonkeyPatch) -> None:
    """``reply_to`` reaches the server as the number of the Message answered.

    Args:
        monkeypatch: Patching helper from pytest.
    """
    api = RecordingApi()
    monkeypatch.setattr(mcp_server, "_client", lambda: api)

    result = mcp_server.post_message("T-3", 5, "Yes.", reply_to=2)

    assert result == "Posted #5 in T-3."
    assert api.sent == [
        (
            "POST",
            "/topics/3/messages",
            {
                "number": 5,
                "body": "Yes.",
                "to": None,
                "file_ids": [],
                "kind": "message",
                "as_human": False,
                "reply_to": 2,
            },
        )
    ]
