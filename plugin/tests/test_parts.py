"""Tests of the plugin's parts that do not need a server."""

import asyncio
import itertools
import stat
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from coloqo import config, mcp_server
from coloqo import watch as watch_module
from coloqo.api import Project, _file_name
from coloqo.render import file_ref, message_text, size, topic_line, topic_ref, topic_text
from coloqo.watch import Me, describe, frames, restored

ME = Me(pseudonym="alice", assistant="k-mine", project="p-mine")
OTHER = "k-other"


@pytest.mark.parametrize("value", ["T-12", "t12", "12", " T-12 ", 12])
def test_topic_ref_accepts_common_forms(value: str | int) -> None:
    """A Topic is named by ``T-12`` in any case, or by its number.

    Args:
        value: A reference.
    """
    assert topic_ref(value, "acme") == ("acme", 12)


@pytest.mark.parametrize(
    "value",
    [
        "globex/T-12",
        "globex/12",
        "https://app.coloqo.team/team/globex/topic/12",
        "see https://app.coloqo.team/team/globex/topic/12#m-5",
    ],
)
def test_topic_ref_names_another_team(value: str) -> None:
    """Another Team's Topic is named with its slug, or by its address (decision 0025).

    Args:
        value: A reference.
    """
    assert topic_ref(value, "acme") == ("globex", 12)


def test_topic_ref_refuses_other_text() -> None:
    """A reference that is not a Topic, or names no Team when none is linked, raises."""
    with pytest.raises(ValueError):
        topic_ref("Q-3", "acme")
    with pytest.raises(ValueError):
        topic_ref("T-3", None)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("3", ("acme", 3)),
        ("file 3", ("acme", 3)),
        ("globex/file 3", ("globex", 3)),
        (3, ("acme", 3)),
    ],
)
def test_file_ref(value: str | int, expected: tuple[str, int]) -> None:
    """A file is named by its number in the Team, or with another Team's slug.

    Args:
        value: A reference.
        expected: The Team and the number.
    """
    assert file_ref(value, "acme") == expected


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
        "team": "acme",
        "ref": "T-3",
        "title": "Rename",
        "number": 4,
        "author": "bob",
        "assistant": "bob · web · vega",
        "author_assistant": OTHER,
        "to": None,
        "to_assistant": None,
        "assistants": [],
    }
    return {**base, **data}


def test_watch_reports_messages_to_me() -> None:
    """A Message addressed to the user or to this Assistant is reported."""
    to_user = describe("message", _message(to="alice"), ME)
    to_assistant = describe("message", _message(to="alice", to_assistant="k-mine"), ME)

    assert to_user is not None and "to you" in to_user and "after=3" in to_user
    assert to_assistant is not None and "to you" in to_assistant


def test_watch_reports_topics_i_take_part_in() -> None:
    """A Message for everyone in a Topic this Assistant holds or wrote in is reported."""
    line = describe("message", _message(assistants=["k-mine", OTHER]), ME)

    assert line is not None and "to you" not in line


def test_watch_ignores_the_rest() -> None:
    """Own Messages, Messages to someone else and unrelated Topics are not reported."""
    own = _message(author_assistant="k-mine", to="alice")
    to_other = _message(assistants=["k-mine"], to="carol")
    unrelated = _message()
    opening = _message(number=1, to="alice")
    before_slugs = {k: v for k, v in _message(to="alice").items() if k != "team"}

    for data in (own, to_other, unrelated, opening, before_slugs):
        assert describe("message", data, ME) is None


def test_watch_tells_of_a_message_for_another_session_of_the_user() -> None:
    """A Message to the user through another session is told, as that session's (0029)."""
    data = _message(to="alice", to_assistant="k-sibling", to_assistant_name="alice · api · chime")

    line = describe("message", data, ME) or ""

    assert "for alice · api · chime, another session of your user; it answers" in line
    assert "to you" not in line


def test_watch_marks_a_message_meant_for_an_offline_session() -> None:
    """A Message that went to the user because its session was offline says so (0029)."""
    data = _message(to="alice", meant_for="alice · api · chime")

    line = describe("message", data, ME) or ""

    assert "to you (meant for alice · api · chime, which is offline)" in line


def test_watch_tells_the_former_holder_its_topic_was_taken() -> None:
    """Taking a Topic over is told to the session that held it, and to nobody else (0024)."""
    taken = _message(kind="taken", **{"from": "k-mine"})

    assert "took T-3 «Rename» over from you" in (describe("message", taken, ME) or "")
    assert describe("message", _message(kind="taken", **{"from": OTHER}), ME) is None


def test_watch_tells_a_sibling_of_an_idle_topic() -> None:
    """An idle notice reaches the holder and the other sessions of its project (0024)."""
    idle = {"team": "acme", "ref": "T-3", "title": "Rename", "closes_at": "2026-11-20T00:00"}

    mine = describe(
        "topic_idle",
        {**idle, "holder": "k-mine", "holder_project": "p-mine", "holder_live": True},
        ME,
    )
    sibling = describe("topic_idle", {**idle, "holder": "k-gone", "holder_project": "p-mine"}, ME)
    live_sibling = describe(
        "topic_idle",
        {**idle, "holder": "k-on", "holder_project": "p-mine", "holder_live": True},
        ME,
    )
    foreign = describe("topic_idle", {**idle, "holder": OTHER, "holder_project": "p-x"}, ME)

    assert mine is not None and "another session" not in mine
    assert sibling is not None and "held by another session of this project" in sibling
    assert live_sibling is None
    assert foreign is None


def test_a_takeover_names_the_former_holder_once() -> None:
    """A takeover line reads as one line: the former holder is in its head, not repeated."""
    taken = {
        "number": 4,
        "kind": "taken",
        "author": "alice",
        "assistant": "alice · api · piano",
        "body": "alice · api · allegro",
        "files": [],
        "created_at": "2026-10-20T19:50:00+00:00",
    }

    text = message_text(taken)

    assert text.count("alice · api · allegro") == 1
    assert "took the Topic over from alice · api · allegro" in text


def test_watch_reports_new_topics_except_own() -> None:
    """New Topics are reported, addressed ones as such; not the Assistant's own."""
    topic = {"team": "acme", "ref": "T-3", "title": "Rename", "area": "Canon", "author": "bob"}

    assert "new topic" in (describe("topic", {**topic, "author_assistant": OTHER}, ME) or "")
    assert "addressed to you" in (
        describe("topic", {**topic, "author_assistant": OTHER, "to": "alice"}, ME) or ""
    )
    assert describe("topic", {**topic, "author_assistant": "k-mine"}, ME) is None


def test_watch_tells_of_topics_for_other_sessions_and_offline_ones() -> None:
    """A Topic opened for another session of the user, or for an offline one, says so (0029)."""
    topic = {"team": "acme", "ref": "T-3", "title": "Rename", "area": "Canon", "author": "bob"}
    sibling = {**topic, "to": "alice", "to_assistant": "k-sibling", "to_assistant_name": "chime"}
    meant = {**topic, "to": "alice", "meant_for": "chime"}

    assert "for chime, another session of your user" in (describe("topic", sibling, ME) or "")
    assert "addressed to you (meant for chime, which is offline)" in (
        describe("topic", meant, ME) or ""
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
                    "human_part": "with",
                    "body": "Yes.",
                    "files": [],
                    "created_at": "2026-10-19T08:05:00+00:00",
                },
            ],
        }
    )

    assert "#1 alice (human) → bob" in text
    assert "#2 bob · web ↪ #1 [with bob]" in text
    assert text.endswith("To reply, post with number=3.")


class RecordingApi:
    """Stands in for the server: records what a tool sends and answers like it.

    Attributes:
        sent: ``(method, path, json)`` of every request.
        team: The Team the project is linked to.
    """

    def __init__(self) -> None:
        """Start with nothing sent."""
        self.sent: list[tuple[str, str, Any]] = []
        self.team = "acme"

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
            "/team/acme/topic/3/message",
            {
                "number": 5,
                "body": "Yes.",
                "to": None,
                "files": [],
                "kind": "message",
                "as_human": False,
                "with_human": False,
                "reply_to": 2,
            },
        )
    ]


def test_post_message_in_another_team_names_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """A Topic of another Team is written to by its slug, and the answer names it so.

    Args:
        monkeypatch: Patching helper from pytest.
    """
    api = RecordingApi()
    monkeypatch.setattr(mcp_server, "_client", lambda: api)

    result = mcp_server.post_message("globex/T-3", 5, "Yes.")

    assert result == "Posted #5 in globex/T-3."
    assert api.sent[0][1] == "/team/globex/topic/3/message"


class AnsweringApi(RecordingApi):
    """A stand-in that answers like the server for stages and closing."""

    def request(self, method: str, path: str, json: Any = None) -> dict[str, Any]:
        """Record a request and answer with what the tool reads back.

        Args:
            method: HTTP method.
            path: API path.
            json: Request body.
        """
        self.sent.append((method, path, json))
        return {"number": 6, "ref": "T-3", "title": "Fix", "deletes_at": "2026-10-27T10:00:00Z"}


def test_stage_and_closing_send_what_the_server_expects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A stage goes without a number; closing carries the outcome.

    Args:
        monkeypatch: Patching helper from pytest.
    """
    api = AnsweringApi()
    monkeypatch.setattr(mcp_server, "_client", lambda: api)

    staged = mcp_server.note_stage("T-3", "Testing")
    closed = mcp_server.close_topic("T-3", "Fixed in ACME-42, MR !17")

    assert api.sent == [
        ("POST", "/team/acme/topic/3/stage", {"text": "Testing"}),
        (
            "PATCH",
            "/team/acme/topic/3",
            {"status": "closed", "outcome": "Fixed in ACME-42, MR !17"},
        ),
    ]
    assert staged == "Stage noted as #6."
    assert closed.endswith("deleted on 2026-10-27.")


def test_the_mcp_texts_carry_the_task_rules() -> None:
    """The instructions and the tool descriptions say what the briefing says (decision 0023)."""
    tools = {t.name: t.description or "" for t in asyncio.run(mcp_server.mcp.list_tools())}

    assert "standing consent" in mcp_server.INSTRUCTIONS
    assert "someone else holds a Topic for, say so in that Topic" in mcp_server.INSTRUCTIONS
    assert "names the main one in `issue`" in mcp_server.INSTRUCTIONS
    assert "different kind of work" in tools["note_stage"]
    assert "a batch finished" in tools["close_topic"]


def test_restored_connection_is_told_only_in_a_linked_project() -> None:
    """A long break is told when the stream comes back, unless the project is unlinked."""
    assert restored(True, 13 * 60) == "Coloqo: connection restored after 13 min; check the inbox."
    assert restored(False, 13 * 60) is None
    assert restored(True, 60) is None
    assert restored(True, None) is None


def _inbox(**data: object) -> dict:
    """Return an Inbox Topic with an unread Message addressed to the user.

    Args:
        **data: Fields to override.
    """
    base = {
        "team": "acme",
        "ref": "T-3",
        "title": "Rename",
        "area": "canon",
        "status": "open",
        "last_number": 4,
        "unread": 1,
        "addressed": True,
    }
    return {**base, **data}


def test_inbox_line_tells_whose_session_answers() -> None:
    """An addressed Topic is the session's own unless it went through another one (0029)."""
    through = _inbox(addressed_via="alice · api · chime", addressed_via_key="k-sibling")
    mine = _inbox(addressed_via="alice · api · nunki", addressed_via_key="k-mine")

    assert topic_line(through, "acme", "k-mine").endswith(
        "1 unread, addressed to your user through alice · api · chime, another session, "
        "which answers it"
    )
    assert topic_line(mine, "acme", "k-mine").endswith("1 unread, addressed to you")
    assert topic_line(_inbox(), "acme", "k-mine").endswith("1 unread, addressed to you")


class InboxApi:
    """Stands in for the server of the MCP tools: an Inbox and a Topic just opened.

    Attributes:
        team: The Team the project is linked to.
        assistant_key: This session's Assistant.
    """

    team = "acme"
    assistant_key = "k-mine"

    def request(self, method: str, path: str, json: Any = None) -> Any:
        """Answer the Inbox, or a Topic opened for an offline session.

        Args:
            method: HTTP method.
            path: API path.
            json: Request body.
        """
        if path == "/inbox":
            return [_inbox(addressed_via="alice · api · nunki", addressed_via_key="k-mine")]
        return {
            "ref": "T-4",
            "title": "Order of merges",
            "area_name": "Releases",
            "messages": [{"number": 1, "to": "bob", "meant_for": "bob · web · vega"}],
        }


def test_the_inbox_tool_knows_its_own_session(monkeypatch: pytest.MonkeyPatch) -> None:
    """A question to this very session reads as the session's own in the ``inbox`` tool.

    Args:
        monkeypatch: Patching helper from pytest.
    """
    monkeypatch.setattr(mcp_server, "_client", InboxApi)

    assert mcp_server.inbox().endswith("1 unread, addressed to you")


def test_open_topic_tells_the_sender_of_an_offline_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Opening a Topic for an offline session says who gets its first message (0029).

    Args:
        monkeypatch: Patching helper from pytest.
    """
    monkeypatch.setattr(mcp_server, "_client", InboxApi)

    result = mcp_server.open_topic(
        "releases", "Order of merges", "Which first?", to="bob · web · vega"
    )

    assert "bob · web · vega is offline, so the message went to bob" in result


def test_a_message_meant_for_an_offline_session_reads_so() -> None:
    """In a Topic's text, a readdressed Message names the session it was meant for (0029)."""
    message = {
        "number": 4,
        "kind": "message",
        "author": "bob",
        "assistant": "bob · web · vega",
        "to": "alice",
        "to_assistant": None,
        "meant_for": "alice · api · chime",
        "body": "Which goes first?",
        "files": [],
        "created_at": "2026-10-21T19:00:00+00:00",
    }

    head = message_text(message).splitlines()[0]

    assert "→ alice (meant for alice · api · chime, which was offline)" in head


def test_post_message_tells_the_sender_of_an_offline_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The sender learns that the session it addressed is offline and who gets it (0029).

    Args:
        monkeypatch: Patching helper from pytest.
    """
    api = RecordingApi()
    answer = {"number": 5, "files": [], "to": "alice", "meant_for": "alice · api · chime"}
    monkeypatch.setattr(api, "request", lambda method, path, json=None: answer)
    monkeypatch.setattr(mcp_server, "_client", lambda: api)

    result = mcp_server.post_message("T-3", 5, "Which first?", to="alice · api · chime")

    assert result.startswith("Posted #5 in T-3.")
    assert "alice · api · chime is offline, so the message went to alice" in result


class Stream:
    """A stream of a few frames, then the end of the connection."""

    status_code = 200

    def __init__(self, lines: list[str]) -> None:
        """Keep the lines to give.

        Args:
            lines: The stream's lines.
        """
        self.lines = lines

    def __enter__(self) -> "Stream":
        """Open it."""
        return self

    def __exit__(self, *_: object) -> None:
        """Close it."""

    def raise_for_status(self) -> None:
        """Pass: the status is fine."""

    def iter_lines(self) -> Iterator[str]:
        """Give the lines."""
        yield from self.lines


class StreamingApi:
    """Stands in for the server of the watch: one stream of heartbeats, then a break.

    Attributes:
        sent: ``(method, path)`` of every request.
    """

    def __init__(self, timeout: float) -> None:
        """Start with nothing sent.

        Args:
            timeout: Ignored.
        """
        self.sent: list[tuple[str, str]] = []
        self.assistant_key = "k-mine"
        self.project_key = "p-mine"
        self.team = "acme"
        heartbeat = ["event: heartbeat", 'data: {"last": "acme:1"}', ""]
        self.http = self
        self.lines = ["event: ready", 'data: {"last": "acme:1"}', ""] + heartbeat * 6

    def register(self, project: Project) -> str:
        """Register the session.

        Args:
            project: The project.
        """
        return "alice · api · nunki"

    def request(self, method: str, path: str) -> dict[str, Any]:
        """Record a request.

        Args:
            method: HTTP method.
            path: API path.
        """
        self.sent.append((method, path))
        return {"pseudonym": "alice"}

    def stream(self, method: str, path: str, **_: object) -> Stream:
        """Open the stream.

        Args:
            method: HTTP method.
            path: API path.
        """
        return Stream(self.lines)

    def close(self) -> None:
        """Close the client."""


def test_watch_tells_the_server_its_session_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every 15 seconds the watch asks for its own Assistant, so the server sees it online.

    Args:
        monkeypatch: Patching helper from pytest.
    """
    apis: list[StreamingApi] = []
    clock = itertools.count(0.0, 8.0)

    def make(timeout: float) -> StreamingApi:
        """Make the fake client and keep it."""
        apis.append(StreamingApi(timeout))
        return apis[-1]

    def stop(_: float) -> None:
        """End the watch at its first pause."""
        raise KeyboardInterrupt

    monkeypatch.setattr(watch_module, "Api", make)
    monkeypatch.setattr(watch_module.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(watch_module.time, "sleep", stop)

    with pytest.raises(KeyboardInterrupt):
        watch_module.watch(".")

    assert apis[0].sent == [("GET", "/me")] + [("GET", "/assistant/k-mine")] * 3


class TeamApi:
    """Stands in for the server of ``overview``: one Team, a member with two sessions."""

    team = "acme"
    team_name = "Acme"
    assistant_name = "alice · api · nunki"

    def request(self, method: str, path: str, json: Any = None) -> Any:
        """Answer the Teams, the Team and the Inbox.

        Args:
            method: HTTP method.
            path: API path.
            json: Request body.
        """
        if path == "/team":
            return [{"slug": "acme"}]
        if path == "/inbox":
            return []
        bob = [
            {"name": "bob · web · vega", "online": True},
            {"name": "bob · web · lyra", "online": False},
        ]
        return {
            "name": "Acme",
            "slug": "acme",
            "role": "owner",
            "turn_limit": 10,
            "areas": [],
            "members": [
                {"pseudonym": "bob", "role": "member", "assistants": bob},
                {"pseudonym": "carol", "role": "member", "assistants": []},
            ],
        }


def test_overview_marks_offline_sessions_and_prefers_the_person(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``overview`` tells which sessions are offline and says to address the person (0029).

    Args:
        monkeypatch: Patching helper from pytest.
    """
    monkeypatch.setattr(mcp_server, "_client", TeamApi)

    text = mcp_server.overview()

    assert "address the person by pseudonym; an Assistant by its full name only when" in text
    assert "  bob (member): bob · web · vega, bob · web · lyra (offline)\n" in text
    assert "  carol (member): no sessions lately\n" in text
