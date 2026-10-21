"""Tests of the former paths for plugins older than 0.5.0, kept one release (decision 0025)."""

import hashlib
from collections.abc import Callable, Iterator

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.conftest import ORIGIN, Plugin, Setup


@pytest.fixture
def old(app: FastAPI, setup: Setup) -> Iterator[TestClient]:
    """Alice's plugin 0.4.0 in the project ``billing-api``: the former paths, no sessions.

    Args:
        app: The application.
        setup: The Team; its Alice's Assistant shares the computer and the project.
    """
    with TestClient(
        app,
        base_url=ORIGIN,
        headers={
            "Authorization": setup.alice_api.client.headers["Authorization"],
            "X-Coloqo-Plugin": "0.4.0",
        },
    ) as client:
        team_id = client.post(
            "/api/assistants",
            json={
                "project_key": hashlib.sha256(b"billing-api").hexdigest(),
                "project_name": "billing-api",
            },
        )
        assert team_id.status_code == 200, team_id.text
        client.headers["X-Coloqo-Assistant"] = str(team_id.json()["id"])
        yield client


def _team(old: TestClient) -> dict:
    """Return the Team as plugin 0.4.0 sees it, with database ids.

    Args:
        old: The old plugin.
    """
    (team,) = old.get("/api/teams").json()
    return old.get(f"/api/teams/{team['id']}").json()


def test_old_plugin_registers_into_the_linked_project(old: TestClient, setup: Setup) -> None:
    """Plugin 0.4.0 registers one Assistant per project, linked like the project's sessions.

    Args:
        old: The old plugin.
        setup: The Team.
    """
    team = _team(old)
    me = old.get("/api/me").json()

    assert (team["name"], team["areas"][0]["name"]) == ("Acme", "Contracts")
    assert isinstance(team["id"], int) and isinstance(team["areas"][0]["id"], int)
    assert isinstance(me["id"], int)
    assert me["assistant"].startswith("alice · billing-api · ")


def test_old_plugin_works_a_topic_through(old: TestClient, setup: Setup) -> None:
    """Open, reply, take over, note a stage, close, read: the former paths and shapes work.

    Args:
        old: The old plugin.
        setup: The Team.
    """
    area_id = _team(old)["areas"][0]["id"]
    opened = old.post(
        f"/api/areas/{area_id}/topics", json={"title": "Q", "body": "Took it", "to": "bob"}
    ).json()
    tid = opened["id"]
    number = setup.bob.get(f"/api/team/{setup.team}/topic").json()[0]["number"]
    setup.bob_web.client.post(f"/api/team/{setup.team}/topic/{number}/hold")
    file_id = old.post(
        f"/api/topics/{tid}/files", content=b"x", headers={"X-File-Name": "x.txt"}
    ).json()["id"]
    reply = old.post(
        f"/api/topics/{tid}/messages",
        json={"number": 3, "body": "with a file", "file_ids": [file_id]},
    )
    late = old.post(f"/api/topics/{tid}/messages", json={"number": 3, "body": "again"})
    old.post(f"/api/topics/{tid}/hold")
    old.post(f"/api/topics/{tid}/stage", json={"text": "code"})
    closed = old.patch(f"/api/topics/{tid}", json={"status": "closed", "outcome": "Done"}).json()
    read = old.get(f"/api/topics/{tid}").json()
    web = setup.alice.get(f"/api/team/{setup.team}/topic/{number}").json()

    assert opened["ref"] == f"T-{tid}"
    assert reply.status_code == 201, reply.text
    assert reply.json()["files"][0]["id"] == file_id
    assert late.json()["detail"]["code"] == "number_taken"
    assert "assistant_id" in late.json()["detail"]["unread"][0]
    assert closed["status"] == "closed"
    assert [m["kind"] for m in read["messages"]] == [
        "message",
        "stage",
        "message",
        "stage",
        "stage",
        "closed",
    ]
    assert [m["kind"] for m in web["messages"]][1:] == [
        "taken",
        "message",
        "taken",
        "stage",
        "closed",
    ]
    assert [m["human_part"] for m in web["messages"]][:3] == [None, None, None]


def test_old_plugin_gets_the_former_inbox_and_briefing(old: TestClient, setup: Setup) -> None:
    """The shared paths answer plugin 0.4.0 in the former shape and tell it to update.

    Args:
        old: The old plugin.
        setup: The Team.
    """
    setup.bob.post(
        f"/api/team/{setup.team}/topic",
        json={"area": setup.area, "title": "Q", "body": "Hi", "to": "alice"},
    )

    (entry,) = old.get("/api/inbox").json()
    briefing = old.get("/api/briefing").json()

    assert entry["ref"] == f"T-{entry['id']}"
    assert isinstance(entry["team_id"], int)
    assert isinstance(briefing["team_id"], int)
    assert briefing["text"].startswith("Coloqo: this session's plugin is older than 0.5.0")
    assert "A Topic here is T-12" not in briefing["text"]


def test_old_plugin_hears_the_former_events(old: TestClient, setup: Setup, live_url: str) -> None:
    """The stream gives plugin 0.4.0 the former data with ids, and nothing of the new.

    Args:
        old: The old plugin.
        setup: The Team.
        live_url: Address of the same application served by uvicorn.
    """
    headers = {
        k: old.headers[k] for k in ("Authorization", "X-Coloqo-Assistant", "X-Coloqo-Plugin")
    }
    setup.bob.post(
        f"/api/team/{setup.team}/topic",
        json={"area": setup.area, "title": "Q", "body": "Hi", "to": "alice"},
    )

    frames = []
    with (
        httpx.Client(base_url=live_url, headers=headers, timeout=10) as client,
        client.stream("GET", "/api/events?after=acme:0") as stream,
    ):
        for line in stream.iter_lines():
            frames.append(line)
            if line.startswith("data:") and '"number"' in line:
                break

    data = frames[-1]
    assert '"topic_id"' in data
    assert '"to_user_id"' in data
    assert '"team": "acme"' not in data
    assert "legacy" not in data


def test_a_new_plugin_does_not_get_the_former_paths_mixed_in(
    setup: Setup, plugin: Callable[..., Plugin]
) -> None:
    """A plugin 0.5.0 gets the new shapes on the shared paths and no user id.

    Args:
        setup: The Team.
        plugin: Factory of plugin installations.
    """
    me = setup.alice_api.client.get("/api/me").json()
    briefing = setup.alice_api.client.get("/api/briefing").json()

    assert me["id"] is None
    assert briefing["team"] == setup.team
    assert "older than 0.5.0" not in briefing["text"]


def test_the_plugin_s_version_decides_the_shape_without_an_assistant(setup: Setup) -> None:
    """A request naming no Assistant is told apart by the plugin's version alone.

    Args:
        setup: The Team.
    """
    token = setup.alice_api.client.headers["Authorization"]
    client = setup.alice_api.client

    old = client.get("/api/me", headers={"X-Coloqo-Assistant": "", "X-Coloqo-Plugin": "0.4.0"})
    new = client.get("/api/me", headers={"X-Coloqo-Assistant": "", "X-Coloqo-Plugin": "0.5.0"})
    none = client.get("/api/me", headers={"X-Coloqo-Assistant": "", "X-Coloqo-Plugin": ""})

    assert token.startswith("Bearer ")
    assert isinstance(old.json()["id"], int)
    assert new.json()["id"] is None
    assert isinstance(none.json()["id"], int)
