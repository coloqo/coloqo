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
    """Alice and Bob in two Teams, Acme and Globex, with an Area each.

    Attributes:
        alice: Alice's web client.
        bob: Bob's web client.
        acme: The first Team.
        globex: The second Team.
        acme_area: An Area of Acme.
        globex_area: An Area of Globex.
    """

    alice: TestClient
    bob: TestClient
    acme: int
    globex: int
    acme_area: int
    globex_area: int


def _team(owner: TestClient, member: TestClient, name: str) -> tuple[int, int]:
    """Create a Team with an Area and bring a member in.

    Args:
        owner: Its owner.
        member: Who joins.
        name: Its name.
    """
    team = owner.post("/api/teams", json={"name": name}).json()["id"]
    token = owner.post(f"/api/teams/{team}/invites").json()["url"].rsplit("/", 1)[1]
    assert member.post(f"/api/invites/{token}/accept").status_code == 200
    area = owner.post(f"/api/teams/{team}/areas", json={"name": "Dev"}).json()["id"]
    return team, area


@pytest.fixture
def two(human: Callable[[str], TestClient]) -> Two:
    """Build both Teams.

    Args:
        human: Factory of logged-in web clients.
    """
    alice, bob = human("alice"), human("bob")
    acme, acme_area = _team(alice, bob, "Acme")
    globex, globex_area = _team(alice, bob, "Globex")
    return Two(alice, bob, acme, globex, acme_area, globex_area)


def _topic(client: TestClient, area: int) -> int:
    """Open a Topic and return its id.

    Args:
        client: Who opens it.
        area: The Area.
    """
    response = client.post(f"/api/areas/{area}/topics", json={"title": "Q", "body": "Hi"})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_unlinked_assistant_reads_but_does_not_write(
    two: Two, plugin: Callable[..., Plugin]
) -> None:
    """An unlinked project's Assistant reads any of its person's Teams and writes nowhere.

    Args:
        two: The Teams.
        plugin: Factory of plugin installations.
    """
    tid = _topic(two.bob, two.acme_area)
    alice = plugin(two.alice, "notes").client

    read = alice.get(f"/api/topics/{tid}")
    post = alice.post(f"/api/topics/{tid}/messages", json={"number": 2, "body": "x"})
    opened = alice.post(f"/api/areas/{two.acme_area}/topics", json={"title": "Q", "body": "x"})

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
    acme_topic = _topic(two.bob, two.acme_area)
    globex_topic = _topic(two.bob, two.globex_area)
    alice = plugin(two.alice, "acme-api", two.acme).client

    here = alice.post(f"/api/topics/{acme_topic}/messages", json={"number": 2, "body": "x"})
    there = alice.post(f"/api/topics/{globex_topic}/messages", json={"number": 2, "body": "x"})
    looked = alice.get(f"/api/topics/{globex_topic}")

    assert here.status_code == 201
    assert there.status_code == 403
    assert there.json()["detail"]["code"] == "other_team"
    assert looked.status_code == 200


def test_reading_another_team_leaves_its_inbox(two: Two, plugin: Callable[..., Plugin]) -> None:
    """Reading a Topic of another Team through an Assistant does not mark it read.

    Args:
        two: The Teams.
        plugin: Factory of plugin installations.
    """
    tid = two.bob.post(
        f"/api/areas/{two.globex_area}/topics", json={"title": "Q", "body": "Hi", "to": "alice"}
    ).json()["id"]
    acme_assistant = plugin(two.alice, "acme-api", two.acme).client
    globex_assistant = plugin(two.alice, "globex-api", two.globex).client

    acme_assistant.post(f"/api/topics/{tid}/read", json={"number": 1})

    assert [t["id"] for t in two.alice.get("/api/inbox").json()] == [tid]
    assert [t["id"] for t in globex_assistant.get("/api/inbox").json()] == [tid]
    assert acme_assistant.get("/api/inbox").json() == []


def test_file_links_only_an_unlinked_assistant_of_a_member(
    two: Two, human: Callable[[str], TestClient], plugin: Callable[..., Plugin]
) -> None:
    """``.coloqo.json`` links when nothing is linked yet and the person is in the Team.

    Args:
        two: The Teams.
        human: Factory of logged-in web clients.
        plugin: Factory of plugin installations.
    """
    carol = human("carol")
    foreign = plugin(carol, "api", two.acme)
    linked = plugin(two.alice, "api", two.acme)

    again = linked.client.post(
        "/api/assistants",
        json={
            "project_key": hashlib.sha256(b"api").hexdigest(),
            "project_name": "api",
            "team_id": two.globex,
        },
    )

    assert foreign.client.get(f"/api/assistants/{foreign.assistant_id}").json()["team_id"] is None
    assert linked.client.get(f"/api/assistants/{linked.assistant_id}").json()["team"] == "Acme"
    assert again.json()["team_id"] == two.acme


def test_person_links_in_the_web_not_the_plugin(two: Two, plugin: Callable[..., Plugin]) -> None:
    """Only the person, from the web, links or unlinks an Assistant, and only to their Team.

    Args:
        two: The Teams.
        plugin: Factory of plugin installations.
    """
    assistant = plugin(two.alice, "notes")
    path = f"/api/assistants/{assistant.assistant_id}/team"

    by_plugin = assistant.client.put(path, json={"team_id": two.acme})
    by_bob = two.bob.put(path, json={"team_id": two.acme})
    after_bob = two.alice.get(f"/api/assistants/{assistant.assistant_id}").json()["team_id"]
    linked = two.alice.put(path, json={"team_id": two.globex})
    listed = two.alice.get("/api/assistants").json()
    unlinked = two.alice.put(path, json={"team_id": None})

    assert by_plugin.status_code == 403
    assert by_bob.status_code == 404
    assert after_bob is None
    assert linked.json()["team"] == "Globex"
    assert [(a["name"], a["team"]) for a in listed] == [("alice · notes", "Globex")]
    assert unlinked.json()["team_id"] is None


def test_installation_without_assistant_reads_nothing(
    two: Two, plugin: Callable[..., Plugin]
) -> None:
    """The installation token alone opens no Team data.

    Args:
        two: The Teams.
        plugin: Factory of plugin installations.
    """
    client = plugin(two.alice, "notes", two.acme).client
    del client.headers["X-Coloqo-Assistant"]

    assert client.get("/api/teams").status_code == 403
    assert client.get("/api/inbox").status_code == 403


def test_team_lists_and_addresses_only_its_assistants(
    two: Two, plugin: Callable[..., Plugin]
) -> None:
    """An Assistant linked to another Team is not shown in this one, nor addressable there.

    Args:
        two: The Teams.
        plugin: Factory of plugin installations.
    """
    plugin(two.bob, "acme-web", two.acme)
    plugin(two.bob, "globex-web", two.globex)
    team = two.alice.get(f"/api/teams/{two.acme}").json()
    bob = next(m for m in team["members"] if m["pseudonym"] == "bob")

    addressed = two.alice.post(
        f"/api/areas/{two.acme_area}/topics",
        json={"title": "Q", "body": "Hi", "to": "bob · globex-web"},
    )

    assert [a["name"] for a in bob["assistants"]] == ["bob · acme-web"]
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
    client = plugin(two.alice, "acme-api", two.acme).client
    headers = {k: client.headers[k] for k in ("Authorization", "X-Coloqo-Assistant")}
    globex = _topic(two.bob, two.globex_area)
    acme = _topic(two.bob, two.acme_area)

    frames = []
    with (
        httpx.Client(base_url=live_url, headers=headers, timeout=10) as stream_client,
        stream_client.stream("GET", "/api/events?after=0") as stream,
    ):
        for line in stream.iter_lines():
            frames.append(line)
            if line.startswith("data:") and f'"topic_id": {acme}' in line:
                break

    data = "\n".join(f for f in frames if f.startswith("data:"))
    assert f'"topic_id": {acme}' in data
    assert f'"topic_id": {globex}' not in data


def test_migration_links_assistants_that_worked_in_one_team(
    two: Two, plugin: Callable[..., Plugin], settings: Settings
) -> None:
    """Existing Assistants are linked to the one Team they wrote in; the rest stay unlinked.

    Args:
        two: The Teams.
        plugin: Factory of plugin installations.
        settings: Instance settings.
    """
    worker = plugin(two.alice, "acme-api", two.acme)
    _topic(worker.client, two.acme_area)
    both = plugin(two.alice, "both", two.acme)
    _topic(both.client, two.acme_area)
    idle = plugin(two.alice, "idle", two.acme)
    two.alice.put(f"/api/assistants/{both.assistant_id}/team", json={"team_id": two.globex})
    _topic(both.client, two.globex_area)
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
    command.downgrade(config, "0005")

    migrate(settings.database_url, settings.files_dir)
    teams = {a["name"]: a["team_id"] for a in two.alice.get("/api/assistants").json()}

    assert teams[worker.assistant] == two.acme
    assert teams[both.assistant] is None
    assert teams[idle.assistant] is None


def test_briefing_names_the_team_rules_and_held_topics(
    two: Two, plugin: Callable[..., Plugin]
) -> None:
    """A linked session learns its Team, the rules and its Topics; an unlinked one to be quiet.

    Args:
        two: The Teams.
        plugin: Factory of plugin installations.
    """
    linked = plugin(two.alice, "acme-api", two.acme).client
    tid = linked.post(
        f"/api/areas/{two.acme_area}/topics",
        json={"title": "Fix export", "body": "Took ACME-42", "issue": "ACME-42"},
    ).json()["id"]
    unlinked = plugin(two.alice, "notes").client

    text = linked.get("/api/briefing").json()["text"]
    quiet = unlinked.get("/api/briefing").json()

    assert "«alice · acme-api» of alice in the Team «Acme»" in text
    assert "Linking this project to «Acme» is your user's standing consent" in text
    assert "note_stage" in text
    assert f"T-{tid} «Fix export» [ACME-42]" in text
    assert (quiet["team_id"], quiet["text"].startswith("Coloqo: this project is not linked")) == (
        None,
        True,
    )
    assert two.alice.get("/api/briefing").status_code == 403
