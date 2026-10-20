"""Tests of the session focus and the project's link file (decisions 0020, 0022)."""

from pathlib import Path
from typing import ClassVar

import pytest

from coloqo import focus, hooks
from coloqo.api import Api, Project, link_file_team
from coloqo.focus import Focus
from coloqo.watch import Me, deliver, describe

MINE, OTHER = "k-mine", "k-other"
ME = Me(pseudonym="alice", assistant=MINE, project="p-mine")


@pytest.fixture
def config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Keep the plugin's configuration in a temporary directory.

    Args:
        tmp_path: Temporary directory from pytest.
        monkeypatch: Patching helper from pytest.
    """
    monkeypatch.setattr(focus, "config_dir", lambda: tmp_path)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s1")
    return tmp_path


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("all", Focus("all")),
        ("mine", Focus("mine")),
        ("quiet", Focus("quiet")),
        ("bob", Focus("people", ["bob"])),
        ("people: bob, @carol", Focus("people", ["bob", "carol"])),
        ("bob carol", Focus("people", ["bob", "carol"])),
    ],
)
def test_focus_is_read_as_people_write_it(text: str, expected: Focus) -> None:
    """A focus is a mode word or the names of people to follow.

    Args:
        text: As written.
        expected: The focus.
    """
    assert focus.parse(text) == expected


def test_focus_is_kept_per_session(config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Each session keeps its own focus; a new one starts from the computer's default.

    Args:
        config: The configuration directory.
        monkeypatch: Patching helper from pytest.
    """
    focus.save(Focus("people", ["bob"]))
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s2")
    fresh = focus.load()
    (config / "settings.json").write_text('{"default_focus": "mine"}')

    assert focus.load("s1") == Focus("people", ["bob"])
    assert fresh == Focus("all")
    assert focus.load() == Focus("mine")


def _message(**data: object) -> dict:
    """Return a Message event's data.

    Args:
        **data: Fields that differ from a plain Message by bob's Assistant.
    """
    return {
        "team": "acme",
        "ref": "T-3",
        "title": "Rename",
        "number": 4,
        "kind": "message",
        "author": "bob",
        "assistant": "bob · web · vega",
        "author_assistant": OTHER,
        "assistants": [OTHER],
        "holder": OTHER,
        **data,
    }


def test_focus_lets_through_what_it_names() -> None:
    """``mine`` passes this session's Topics, ``people`` their authors, ``quiet`` nothing."""
    involved = _message(assistants=[OTHER, MINE])
    by_carol = _message(author="carol")

    assert focus.allows(Focus("mine"), "message", involved, MINE)
    assert not focus.allows(Focus("mine"), "message", _message(), MINE)
    assert focus.allows(Focus("people", ["Bob"]), "message", _message(), MINE)
    assert not focus.allows(Focus("people", ["bob"]), "message", by_carol, MINE)
    assert not focus.allows(Focus("quiet"), "message", involved, MINE)
    assert focus.allows(Focus("all"), "message", by_carol, MINE)


def test_watch_skips_stages_and_tells_of_inactivity() -> None:
    """Stage lines stay out of sessions; closing for inactivity and its notice come in."""
    stage = describe("message", _message(kind="stage", to="alice"), ME)
    closed = describe(
        "topic_status", {"team": "acme", "ref": "T-3", "title": "Rename", "automatic": True}, ME
    )
    idle = describe(
        "topic_idle",
        {
            "team": "acme",
            "ref": "T-3",
            "title": "Rename",
            "holder": MINE,
            "closes_at": "2026-11-18T10:00:00+00:00",
        },
        ME,
    )

    assert stage is None
    assert closed is not None and "inactivity" in closed
    assert idle is not None and "2026-11-18" in idle and "close_topic" in idle


def test_link_file_is_found_up_to_the_repository(tmp_path: Path) -> None:
    """``.coloqo.json`` is read in the project or a parent, not past the repository's root.

    Args:
        tmp_path: Temporary directory from pytest.
    """
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    (repo / "services" / "api").mkdir(parents=True)
    (repo / ".coloqo.json").write_text('{"team": "acme"}')
    (tmp_path / ".coloqo.json").write_text('{"team": "globex"}')
    other = tmp_path / "other"
    (other / ".git").mkdir(parents=True)
    broken = tmp_path / "broken"
    (broken / ".git").mkdir(parents=True)
    (broken / ".coloqo.json").write_text('{"team": "Acme Corp"}')
    old = tmp_path / "old"
    (old / ".git").mkdir(parents=True)
    (old / ".coloqo.json").write_text('{"team_id": 7, "team": "Acme"}')

    assert link_file_team(repo / "services" / "api") == "acme"
    assert Project.detect(str(repo)).team == "acme"
    assert link_file_team(other) is None
    assert link_file_team(broken) is None
    assert link_file_team(old) == 7


class FakeApi:
    """Stands in for the server at session start.

    Attributes:
        linked: Whether the project is linked to a Team.
        asked: Paths requested.
    """

    linked = True
    asked: ClassVar[list[str]] = []

    def __init__(self, timeout: float) -> None:
        """Start a session with the server.

        Args:
            timeout: Ignored.
        """
        self.assistant_key = MINE
        self.team = "acme" if FakeApi.linked else None

    def register(self, project: Project, session: str | None = None) -> str:
        """Pretend to register.

        Args:
            project: The project.
            session: The session.
        """
        return "alice · api · vega"

    def request(self, method: str, path: str) -> object:
        """Answer the briefing and the Inbox.

        Args:
            method: HTTP method.
            path: API path.
        """
        FakeApi.asked.append(path)
        if path == "/briefing":
            if not FakeApi.linked:
                return {"text": "Coloqo: this project is not linked.", "team": None}
            return {"text": "Coloqo: you are «alice · api» in «Acme».", "team": "acme"}
        return [
            {
                "team": "acme",
                "ref": "T-3",
                "title": "Fix",
                "area": "Dev",
                "status": "open",
                "last_number": 4,
                "unread": 2,
                "addressed": True,
            }
        ]

    def close(self) -> None:
        """Nothing to close."""


def test_session_start_briefs_a_linked_project_only(
    config: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A linked session gets the briefing, its Inbox and focus; an unlinked one a quiet line.

    Args:
        config: The configuration directory.
        monkeypatch: Patching helper from pytest.
        capsys: Captured output from pytest.
    """
    monkeypatch.setattr(hooks, "Api", FakeApi)
    monkeypatch.setattr(hooks, "_input", lambda: {"session_id": "s1"})
    focus.save(Focus("mine"))

    FakeApi.linked, FakeApi.asked = True, []
    hooks.session_start()
    linked = capsys.readouterr().out
    FakeApi.linked, FakeApi.asked = False, []
    hooks.session_start()
    quiet = capsys.readouterr().out

    assert "«alice · api» in «Acme»" in linked
    assert "T-3" in linked
    assert "focus: mine" in linked
    assert quiet.strip() == "Coloqo: this project is not linked."
    assert FakeApi.asked == ["/briefing"]


def test_watch_prints_only_what_the_focus_lets_through(config: Path) -> None:
    """The watch reads the session's focus for each event.

    Args:
        config: The configuration directory.
    """
    to_me = _message(to="alice")

    before = deliver("message", to_me, ME)
    focus.save(Focus("quiet"))
    after = deliver("message", to_me, ME)

    assert before is not None
    assert after is None


def test_register_sends_the_link_files_team(monkeypatch: pytest.MonkeyPatch) -> None:
    """Registration carries the Team the project's ``.coloqo.json`` names, and keeps the answer.

    Args:
        monkeypatch: Patching helper from pytest.
    """
    sent: list[dict] = []

    def request(self: Api, method: str, path: str, json: dict) -> dict:
        """Record the registration and answer like the server.

        Args:
            self: The client.
            method: HTTP method.
            path: API path.
            json: Request body.
        """
        sent.append(json)
        return {
            "key": "k-five",
            "name": "alice · api · vega",
            "word": "vega",
            "project": "api",
            "project_key": "p-api",
            "team": "acme",
            "team_name": "Acme",
        }

    monkeypatch.setattr(Api, "request", request)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s9")
    api = Api(token="t")

    api.register(Project(key="k" * 64, name="api", team="acme"))
    api.register(Project(key="k" * 64, name="api", team=7), session="s1")

    assert sent == [
        {
            "project_key": "k" * 64,
            "project_name": "api",
            "team": "acme",
            "team_id": None,
            "session_id": "s9",
        },
        {
            "project_key": "k" * 64,
            "project_name": "api",
            "team": None,
            "team_id": 7,
            "session_id": "s1",
        },
    ]
    assert (api.assistant_key, api.project_key, api.team, api.team_name) == (
        "k-five",
        "p-api",
        "acme",
        "Acme",
    )
    assert api.http.headers["X-Coloqo-Assistant"] == "k-five"
