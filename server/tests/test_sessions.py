"""Tests of Assistants as sessions: words, renaming, taking over, the briefing (decision 0024)."""

from collections.abc import Callable

from fastapi import FastAPI
from fastapi.testclient import TestClient

from coloqo_server.naming import WORDS
from tests.conftest import Plugin, Setup
from tests.test_topics import _open


def _path(setup: Setup, number: int) -> str:
    """Return a Topic's address in the API.

    Args:
        setup: The Team.
        number: The Topic's number.
    """
    return f"/api/team/{setup.team}/topic/{number}"


def test_each_session_is_its_own_assistant_with_a_word(
    setup: Setup, sibling: Callable[..., Plugin]
) -> None:
    """Sessions of one project are different Assistants with different words.

    Args:
        setup: The Team.
        sibling: Opens another session of a project on the same computer.
    """
    second = sibling(setup.alice_api, "billing-api", "s2")

    assert second.key != setup.alice_api.key
    assert second.word != setup.alice_api.word
    assert {second.word, setup.alice_api.word} <= set(WORDS)
    assert second.assistant == f"alice · billing-api · {second.word}"
    assert second.project_key == setup.alice_api.project_key


def test_registering_again_is_the_same_assistant(
    setup: Setup, sibling: Callable[..., Plugin]
) -> None:
    """The hooks, the tools and the watch of one session register the same Assistant.

    Args:
        setup: The Team.
        sibling: Opens another session of a project on the same computer.
    """
    again = sibling(setup.alice_api, "billing-api", "s1")

    assert (again.key, again.word) == (setup.alice_api.key, setup.alice_api.word)


def test_rename_by_owner_or_session_and_unique_among_live_ones(
    setup: Setup, sibling: Callable[..., Plugin]
) -> None:
    """The owner or the session itself changes the word; a live sibling's word is refused.

    Args:
        setup: The Team.
        sibling: Opens another session of a project on the same computer.
    """
    second = sibling(setup.alice_api, "billing-api", "s2")
    path = f"/api/assistant/{setup.alice_api.key}"

    by_owner = setup.alice.patch(path, json={"word": "Orion"})
    by_session = setup.alice_api.client.patch(path, json={"word": "lyra"})
    taken = setup.alice.patch(path, json={"word": second.word})
    bad = setup.alice.patch(path, json={"word": "9lives"})
    by_bob = setup.bob.patch(path, json={"word": "x"})
    by_sibling = second.client.patch(path, json={"word": "x"})

    assert by_owner.json()["name"] == "alice · billing-api · orion"
    assert by_session.json()["word"] == "lyra"
    assert taken.status_code == 409
    assert bad.status_code == 422
    assert (by_bob.status_code, by_sibling.status_code) == (404, 404)


def test_session_id_is_shown_to_its_owner_only(setup: Setup, plugin: Callable[..., Plugin]) -> None:
    """A Team lists live Assistants; only their owner sees the Claude Code session id.

    Args:
        setup: The Team.
        plugin: Factory of plugin installations.
    """

    def ids(client: TestClient) -> dict[str, str | None]:
        """Return the session ids a viewer sees, by Assistant name.

        Args:
            client: The viewer.
        """
        team = client.get(f"/api/team/{setup.team}").json()
        return {a["name"]: a["session_id"] for m in team["members"] for a in m["assistants"]}

    assert ids(setup.alice)[setup.alice_api.assistant] == "s1"
    assert ids(setup.bob)[setup.alice_api.assistant] is None
    assert ids(setup.bob)[setup.bob_web.assistant] == "s1"


def test_taking_over_leaves_a_line_and_moves_the_stages(
    setup: Setup, sibling: Callable[..., Plugin]
) -> None:
    """Another session takes the Topic over with a line in the feed; then only it notes stages.

    Args:
        setup: The Team.
        sibling: Opens another session of a project on the same computer.
    """
    number = _open(setup)["number"]
    second = sibling(setup.alice_api, "billing-api", "s2")

    refused = second.client.post(f"{_path(setup, number)}/stage", json={"text": "code"})
    held = second.client.post(f"{_path(setup, number)}/hold").json()
    again = second.client.post(f"{_path(setup, number)}/hold")
    old = setup.alice_api.client.post(f"{_path(setup, number)}/stage", json={"text": "x"})
    messages = setup.alice.get(_path(setup, number)).json()["messages"]

    assert refused.json()["detail"]["code"] == "not_holder"
    assert held["holder"] == second.assistant
    assert again.status_code == 200
    assert old.json()["detail"]["code"] == "not_holder"
    assert [(m["kind"], m["assistant"], m["body"]) for m in messages[1:]] == [
        ("taken", second.assistant, setup.alice_api.assistant)
    ]


def test_new_session_hears_of_the_project_s_held_topics(
    setup: Setup, sibling: Callable[..., Plugin]
) -> None:
    """A new session holds nothing and is told what its project's other sessions hold.

    Args:
        setup: The Team.
        sibling: Opens another session of a project on the same computer.
    """
    number = _open(setup)["number"]
    setup.alice_api.client.post(f"{_path(setup, number)}/stage", json={"text": "the MR"})
    second = sibling(setup.alice_api, "billing-api", "s2")

    first_text = setup.alice_api.client.get("/api/briefing").json()["text"]
    second_text = second.client.get("/api/briefing").json()["text"]

    assert f"You hold — continue there and note each stage:\n- T-{number}" in first_text
    assert "You hold no Topic" in second_text
    assert f"T-{number} «Rename field amount» held by «{setup.alice_api.assistant}»" in second_text
    assert "last stage «the MR» on " in second_text
    assert "take it over with hold_topic" in second_text
    assert "Held by other sessions" not in first_text


def test_outdated_plugin_is_told_to_update(setup: Setup, app: FastAPI) -> None:
    """A session older than the latest release is told to update itself; a current one is not.

    Args:
        setup: The Team.
        app: The application, where the latest release is kept.
    """
    app.state.latest_plugin = (0, 5, 1)
    outdated = setup.alice_api.client.get("/api/briefing").json()["text"]
    app.state.latest_plugin = (0, 5, 0)
    current = setup.alice_api.client.get("/api/briefing").json()["text"]
    app.state.latest_plugin = None
    unknown = setup.alice_api.client.get("/api/briefing").json()["text"]

    assert "this session's plugin is 0.5.0, the latest is 0.5.1" in outdated
    assert "claude plugin update coloqo@coloqo" in outdated
    assert "claude plugin update" not in current
    assert "claude plugin update" not in unknown


def test_link_page_by_a_one_time_token(setup: Setup, plugin: Callable[..., Plugin]) -> None:
    """A session asks for a link; its person chooses the Team there once (decision 0025).

    Args:
        setup: The Team.
        plugin: Factory of plugin installations.
    """
    notes = plugin(setup.alice, "notes")
    url = notes.client.post("/api/link").json()["url"]
    token = url.rsplit("/", 1)[1]

    shown = setup.alice.get(f"/api/link/{token}").json()
    by_bob = setup.bob.get(f"/api/link/{token}")
    used = setup.alice.put(f"/api/link/{token}", json={"team": setup.team}).json()
    again = setup.alice.put(f"/api/link/{token}", json={"team": None})
    by_plugin = notes.client.put(f"/api/link/{token}", json={"team": None})

    assert url.startswith("https://testserver/link/")
    assert (shown["project"], shown["installation"], shown["team"], shown["valid"]) == (
        "notes",
        "laptop",
        None,
        True,
    )
    assert by_bob.status_code == 404
    assert (used["team"], used["valid"]) == (setup.team, False)
    assert again.status_code == 410
    assert by_plugin.status_code == 403
    assert notes.client.get(f"/api/assistant/{notes.key}").json()["team"] == setup.team


def test_an_assistant_addressed_by_its_project_name(setup: Setup) -> None:
    """A name without the word, as plugins before sessions knew it, reaches the project.

    Args:
        setup: The Team.
    """
    number = _open(setup)["number"]

    response = setup.bob_web.client.post(
        f"{_path(setup, number)}/message",
        json={"number": 2, "body": "Hi", "to": "alice · billing-api"},
    )

    assert response.json()["to_assistant"] == setup.alice_api.assistant
