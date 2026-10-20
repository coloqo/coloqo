"""Tests of a project linked to one Team: what an Assistant reads, writes and is told (0020)."""

import hashlib
from collections.abc import Callable
from dataclasses import dataclass

import httpx
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from coloqo_server.db import MIGRATIONS_DIR, migrate
from coloqo_server.settings import Settings
from tests.conftest import Plugin


@dataclass
class Two:
    """Alice and Bob in two Teams, Acme and Globex, with an Area ``dev`` each.

    Attributes:
        alice: Alice's web client.
        bob: Bob's web client.
    """

    alice: TestClient
    bob: TestClient


def _team(owner: TestClient, member: TestClient, name: str) -> str:
    """Create a Team with an Area ``dev`` and bring a member in; return its slug.

    Args:
        owner: Its owner.
        member: Who joins.
        name: Its name.
    """
    team = owner.post("/api/team", json={"name": name}).json()["slug"]
    token = owner.post(f"/api/team/{team}/invite").json()["url"].rsplit("/", 1)[1]
    assert member.post(f"/api/invite/{token}/accept").status_code == 200
    assert owner.post(f"/api/team/{team}/area", json={"name": "Dev"}).json()["slug"] == "dev"
    return team


@pytest.fixture
def two(human: Callable[[str], TestClient]) -> Two:
    """Build both Teams.

    Args:
        human: Factory of logged-in web clients.
    """
    alice, bob = human("alice"), human("bob")
    assert _team(alice, bob, "Acme") == "acme"
    assert _team(alice, bob, "Globex") == "globex"
    return Two(alice, bob)


def _topic(client: TestClient, team: str, to: str | None = None) -> int:
    """Open a Topic in the Team's Area ``dev`` and return its number.

    Args:
        client: Who opens it.
        team: The Team's slug.
        to: Addressee of the first Message.
    """
    response = client.post(
        f"/api/team/{team}/topic", json={"area": "dev", "title": "Q", "body": "Hi", "to": to}
    )
    assert response.status_code == 201, response.text
    return response.json()["number"]


def test_unlinked_assistant_reads_but_does_not_write(
    two: Two, plugin: Callable[..., Plugin]
) -> None:
    """An unlinked project's Assistant reads any of its person's Teams and writes nowhere.

    Args:
        two: The Teams.
        plugin: Factory of plugin installations.
    """
    number = _topic(two.bob, "acme")
    alice = plugin(two.alice, "notes").client

    read = alice.get(f"/api/team/acme/topic/{number}")
    post = alice.post(f"/api/team/acme/topic/{number}/message", json={"number": 2, "body": "x"})
    opened = alice.post("/api/team/acme/topic", json={"area": "dev", "title": "Q", "body": "x"})

    assert read.status_code == 200
    assert post.status_code == 403
    assert post.json()["detail"]["code"] == "not_linked"
    assert opened.json()["detail"]["code"] == "not_linked"
    assert alice.get("/api/inbox").json() == []


def test_linked_assistant_writes_only_in_its_team(two: Two, plugin: Callable[..., Plugin]) -> None:
    """A linked Assistant writes in its Team; another Team's Topic it may read, not write.

    Args:
        two: The Teams.
        plugin: Factory of plugin installations.
    """
    acme_topic = _topic(two.bob, "acme")
    globex_topic = _topic(two.bob, "globex")
    alice = plugin(two.alice, "acme-api", "acme").client
    message = {"number": 2, "body": "x"}

    here = alice.post(f"/api/team/acme/topic/{acme_topic}/message", json=message)
    there = alice.post(f"/api/team/globex/topic/{globex_topic}/message", json=message)
    looked = alice.get(f"/api/team/globex/topic/{globex_topic}")

    assert here.status_code == 201
    assert there.status_code == 403
    assert there.json()["detail"]["code"] == "other_team"
    assert looked.status_code == 200


def test_topics_are_numbered_per_team(two: Two) -> None:
    """Each Team numbers its Topics from 1, whatever other Teams open (decision 0025).

    Args:
        two: The Teams.
    """
    numbers = [_topic(two.bob, team) for team in ("acme", "globex", "acme", "globex", "acme")]

    assert numbers == [1, 1, 2, 2, 3]
    assert two.alice.get("/api/team/globex/topic/2").json()["ref"] == "T-2"


def test_reading_another_team_leaves_its_inbox(two: Two, plugin: Callable[..., Plugin]) -> None:
    """Reading a Topic of another Team through an Assistant does not mark it read.

    Args:
        two: The Teams.
        plugin: Factory of plugin installations.
    """
    number = _topic(two.bob, "globex", to="alice")
    acme_assistant = plugin(two.alice, "acme-api", "acme").client
    globex_assistant = plugin(two.alice, "globex-api", "globex").client

    acme_assistant.post(f"/api/team/globex/topic/{number}/read", json={"number": 1})

    assert [(t["team"], t["number"]) for t in two.alice.get("/api/inbox").json()] == [
        ("globex", number)
    ]
    assert [t["number"] for t in globex_assistant.get("/api/inbox").json()] == [number]
    assert acme_assistant.get("/api/inbox").json() == []


def test_file_links_only_an_unlinked_project_of_a_member(
    two: Two, human: Callable[[str], TestClient], plugin: Callable[..., Plugin]
) -> None:
    """``.coloqo.json`` links when nothing is linked yet and the person is in the Team.

    Args:
        two: The Teams.
        human: Factory of logged-in web clients.
        plugin: Factory of plugin installations.
    """
    carol = human("carol")
    foreign = plugin(carol, "api", "acme")
    linked = plugin(two.alice, "api", "acme")

    again = linked.client.post(
        "/api/assistant",
        json={
            "project_key": hashlib.sha256(b"api").hexdigest(),
            "project_name": "api",
            "team": "globex",
            "session_id": "s2",
        },
    )

    assert foreign.client.get(f"/api/assistant/{foreign.key}").json()["team"] is None
    assert linked.client.get(f"/api/assistant/{linked.key}").json()["team_name"] == "Acme"
    assert again.json()["team"] == "acme"


def test_person_links_in_the_web_not_the_plugin(two: Two, plugin: Callable[..., Plugin]) -> None:
    """Only the person, from the web, links or unlinks a project, and only to their Team.

    Args:
        two: The Teams.
        plugin: Factory of plugin installations.
    """
    assistant = plugin(two.alice, "notes")
    path = f"/api/project/{assistant.project_key}/team"

    by_plugin = assistant.client.put(path, json={"team": "acme"})
    by_bob = two.bob.put(path, json={"team": "acme"})
    after_bob = assistant.client.get(f"/api/assistant/{assistant.key}").json()["team"]
    linked = two.alice.put(path, json={"team": "globex"})
    listed = two.alice.get("/api/project").json()
    unlinked = two.alice.put(path, json={"team": None})

    assert by_plugin.status_code == 403
    assert by_bob.status_code == 404
    assert after_bob is None
    assert linked.json()["team_name"] == "Globex"
    assert [(p["name"], p["team"], [a["name"] for a in p["assistants"]]) for p in listed] == [
        ("notes", "globex", [assistant.assistant])
    ]
    assert unlinked.json()["team"] is None


def test_a_link_holds_for_every_session_of_the_project(
    two: Two, plugin: Callable[..., Plugin], sibling: Callable[..., Plugin]
) -> None:
    """A link chosen in the browser belongs to the project, not to one session (0024).

    Args:
        two: The Teams.
        plugin: Factory of plugin installations.
        sibling: Opens another session of a project on the same computer.
    """
    first = plugin(two.alice, "notes", session="one")
    two.alice.put(f"/api/project/{first.project_key}/team", json={"team": "acme"})

    second = sibling(first, "notes", "two")

    assert second.project_key == first.project_key
    assert second.key != first.key
    assert second.client.get(f"/api/assistant/{second.key}").json()["team"] == "acme"


def test_installation_without_assistant_reads_nothing(
    two: Two, plugin: Callable[..., Plugin]
) -> None:
    """The installation token alone opens no Team data.

    Args:
        two: The Teams.
        plugin: Factory of plugin installations.
    """
    client = plugin(two.alice, "notes", "acme").client
    del client.headers["X-Coloqo-Assistant"]

    assert client.get("/api/team").status_code == 403
    assert client.get("/api/inbox").status_code == 403


def test_team_lists_and_addresses_only_its_assistants(
    two: Two, plugin: Callable[..., Plugin]
) -> None:
    """An Assistant linked to another Team is not shown in this one, nor addressable there.

    Args:
        two: The Teams.
        plugin: Factory of plugin installations.
    """
    acme_web = plugin(two.bob, "acme-web", "acme")
    globex_web = plugin(two.bob, "globex-web", "globex")
    team = two.alice.get("/api/team/acme").json()
    bob = next(m for m in team["members"] if m["pseudonym"] == "bob")

    addressed = two.alice.post(
        "/api/team/acme/topic",
        json={"area": "dev", "title": "Q", "body": "Hi", "to": globex_web.assistant},
    )

    assert [a["name"] for a in bob["assistants"]] == [acme_web.assistant]
    assert addressed.status_code == 422


def test_stream_brings_only_the_linked_team(
    two: Two, plugin: Callable[..., Plugin], live_url: str
) -> None:
    """A linked Assistant's stream carries its Team's events and skips the other Team's.

    Args:
        two: The Teams.
        plugin: Factory of plugin installations.
        live_url: Address of the same application served by uvicorn.
    """
    client = plugin(two.alice, "acme-api", "acme").client
    headers = {
        k: client.headers[k] for k in ("Authorization", "X-Coloqo-Assistant", "X-Coloqo-Plugin")
    }
    _topic(two.bob, "globex")
    _topic(two.bob, "acme")

    frames = []
    with (
        httpx.Client(base_url=live_url, headers=headers, timeout=10) as stream_client,
        stream_client.stream("GET", "/api/events?after=0") as stream,
    ):
        for line in stream.iter_lines():
            frames.append(line)
            if line.startswith("data:") and '"team": "acme"' in line:
                break

    data = "\n".join(f for f in frames if f.startswith("data:"))
    assert '"team": "acme"' in data
    assert '"team": "globex"' not in data
    assert "_team_id" not in data


def test_migration_links_projects_that_worked_in_one_team(
    two: Two, plugin: Callable[..., Plugin], settings: Settings
) -> None:
    """Migrating up again links the project that wrote in one Team; the rest stay unlinked.

    Args:
        two: The Teams.
        plugin: Factory of plugin installations.
        settings: Instance settings.
    """
    worker = plugin(two.alice, "acme-api", "acme")
    _topic(worker.client, "acme")
    both = plugin(two.alice, "both", "acme")
    _topic(both.client, "acme")
    plugin(two.alice, "idle", "acme")
    two.alice.put(f"/api/project/{both.project_key}/team", json={"team": "globex"})
    _topic(both.client, "globex")
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
    command.downgrade(config, "0005")

    migrate(settings.database_url, settings.files_dir)
    teams = {p["name"]: p["team"] for p in two.alice.get("/api/project").json()}

    assert teams == {"acme-api": "acme", "both": None, "idle": None}


def test_briefing_names_the_team_rules_and_held_topics(
    two: Two, plugin: Callable[..., Plugin]
) -> None:
    """A linked session learns its Team, the rules and its Topics; an unlinked one to be quiet.

    Args:
        two: The Teams.
        plugin: Factory of plugin installations.
    """
    linked = plugin(two.alice, "acme-api", "acme")
    number = linked.client.post(
        "/api/team/acme/topic",
        json={"area": "dev", "title": "Fix export", "body": "Took ACME-42", "issue": "ACME-42"},
    ).json()["number"]
    unlinked = plugin(two.alice, "notes").client

    text = linked.client.get("/api/briefing").json()["text"]
    quiet = unlinked.get("/api/briefing").json()

    assert f"«{linked.assistant}» of alice in the Team «Acme» (acme)" in text
    assert "Linking this project to «Acme» is your user's standing consent" in text
    assert "note_stage" in text
    assert f"T-{number} «Fix export» [ACME-42]" in text
    assert "https://testserver/team/acme/topic/12" in text
    assert (quiet["team"], quiet["text"].startswith("Coloqo: this project is not linked")) == (
        None,
        True,
    )
    assert two.alice.get("/api/briefing").status_code == 403
