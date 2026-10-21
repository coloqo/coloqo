"""Tests of which sessions are online, which are shown, and whom a Message reaches (0029)."""

from collections.abc import Callable
from datetime import timedelta

from coloqo_server.settings import Settings
from tests.conftest import Plugin, Setup, _connect
from tests.test_retention import _age, _tend
from tests.test_topics import _open


def _away(settings: Settings, assistant: Plugin, minutes: float) -> None:
    """Move an Assistant's last request back, as if its session had been gone that long.

    Args:
        settings: Instance settings.
        assistant: The Assistant; its client must not be used afterwards.
        minutes: How long ago.
    """
    with _connect(settings.database_url) as connection:
        connection.execute(
            "UPDATE assistants SET last_seen_at = now() - %s WHERE key = %s",
            (timedelta(minutes=minutes), assistant.key),
        )


def _post(setup: Setup, number: int, to: str) -> dict:
    """Post Bob's Assistant's next Message in a Topic, addressed to ``to``.

    Args:
        setup: The Team.
        number: The Topic's number.
        to: The addressee.
    """
    path = f"/api/team/{setup.team}/topic/{number}"
    next_number = setup.bob_web.client.get(path).json()["last_number"] + 1
    response = setup.bob_web.client.post(
        f"{path}/message", json={"number": next_number, "body": "Which goes first?", "to": to}
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_online_shown_and_forgotten(
    setup: Setup, settings: Settings, sibling: Callable[..., Plugin]
) -> None:
    """A session is online for a minute after its request, shown for 20 minutes, then gone.

    Args:
        setup: The Team.
        settings: Instance settings.
        sibling: Opens another session of a project on the same computer.
    """
    away = sibling(setup.alice_api, "billing-api", "s2")
    gone = sibling(setup.alice_api, "billing-api", "s3")
    _away(settings, away, 2)
    _away(settings, gone, 21)

    team = setup.bob.get(f"/api/team/{setup.team}").json()
    alice = next(m for m in team["members"] if m["pseudonym"] == "alice")
    shown = {a["word"]: a["online"] for a in alice["assistants"]}
    (project,) = setup.alice.get("/api/project").json()
    listed = {a["word"]: a["online"] for a in project["assistants"]}

    assert shown == {setup.alice_api.word: True, away.word: False}
    assert listed == shown


def test_a_message_to_an_offline_session_goes_to_its_person(
    setup: Setup, settings: Settings, sibling: Callable[..., Plugin]
) -> None:
    """Addressed to a session gone for a minute or more, a Message is its person's, marked.

    Args:
        setup: The Team.
        settings: Instance settings.
        sibling: Opens another session of a project on the same computer.
    """
    number = _open(setup)["number"]
    away = sibling(setup.alice_api, "billing-api", "s2")
    _away(settings, away, 2)

    posted = _post(setup, number, away.assistant)
    (inbox,) = setup.alice.get("/api/inbox").json()
    with _connect(settings.database_url) as connection:
        (data,) = connection.execute(
            "SELECT data FROM events WHERE kind = 'message' ORDER BY number DESC LIMIT 1"
        ).fetchone()

    assert (posted["to"], posted["to_assistant"]) == ("alice", None)
    assert posted["meant_for"] == away.assistant
    assert (inbox["addressed"], inbox["addressed_via"]) == (True, None)
    assert (data["to"], data["to_assistant"], data["meant_for"]) == (
        "alice",
        None,
        away.assistant,
    )


def test_a_message_to_an_online_session_is_that_session_s(setup: Setup) -> None:
    """Addressed to a running session, a Message is that session's; the Inbox says which.

    Args:
        setup: The Team.
    """
    number = _open(setup)["number"]

    posted = _post(setup, number, setup.alice_api.assistant)
    (inbox,) = setup.alice.get("/api/inbox").json()

    assert (posted["to_assistant"], posted["meant_for"]) == (setup.alice_api.assistant, None)
    assert (inbox["addressed_via"], inbox["addressed_via_key"]) == (
        setup.alice_api.assistant,
        setup.alice_api.key,
    )


def test_a_topic_opened_for_an_offline_session_goes_to_its_person(
    setup: Setup, settings: Settings, plugin: Callable[..., Plugin]
) -> None:
    """The first Message of a Topic is addressed the same way as any other.

    Args:
        setup: The Team.
        settings: Instance settings.
        plugin: Factory of plugin installations.
    """
    bob_cli = plugin(setup.bob, "cli", setup.team)
    _away(settings, bob_cli, 2)

    topic = _open(setup, to=bob_cli.assistant)
    first = topic["messages"][0]
    with _connect(settings.database_url) as connection:
        (data,) = connection.execute(
            "SELECT data FROM events WHERE kind = 'topic' ORDER BY number DESC LIMIT 1"
        ).fetchone()

    assert (first["to"], first["to_assistant"], first["meant_for"]) == (
        "bob",
        None,
        bob_cli.assistant,
    )
    assert (data["to_assistant"], data["meant_for"]) == (None, bob_cli.assistant)


def test_unknown_addressee_is_offered_shown_names_only(
    setup: Setup, settings: Settings, sibling: Callable[..., Plugin]
) -> None:
    """The names offered for an unknown addressee leave forgotten sessions out.

    Args:
        setup: The Team.
        settings: Instance settings.
        sibling: Opens another session of a project on the same computer.
    """
    number = _open(setup)["number"]
    gone = sibling(setup.alice_api, "billing-api", "s2")
    _away(settings, gone, 21)

    response = setup.bob_web.client.post(
        f"/api/team/{setup.team}/topic/{number}/message",
        json={"number": 2, "body": "Hi", "to": "carol"},
    )

    assert response.status_code == 422
    assert setup.alice_api.assistant in response.json()["detail"]
    assert gone.assistant not in response.json()["detail"]


def test_idle_warning_says_whether_the_holder_is_online(setup: Setup, settings: Settings) -> None:
    """The idle warning's holder is live only while its session runs.

    Args:
        setup: The Team.
        settings: Instance settings.
    """
    tid = _open(setup)["number"]
    _age(settings, tid, "updated_at", 28)
    _away(settings, setup.alice_api, 2)

    _tend(settings)
    with _connect(settings.database_url) as connection:
        (data,) = connection.execute(
            "SELECT data FROM events WHERE kind = 'topic_idle' LIMIT 1"
        ).fetchone()

    assert data["holder_live"] is False
