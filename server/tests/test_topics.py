"""Tests of Teams, Areas, Topics, Messages, the Inbox and files."""

import time
from collections.abc import Callable, Iterator
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
class Setup:
    """A Team of alice (owner) and bob, an Area, and an Assistant each.

    Attributes:
        alice: Alice's web client.
        bob: Bob's web client.
        alice_api: Alice's Assistant.
        bob_web: Bob's Assistant.
        team_id: The Team.
        area_id: The Area.
    """

    alice: TestClient
    bob: TestClient
    alice_api: Plugin
    bob_web: Plugin
    team_id: int
    area_id: int


@pytest.fixture
def setup(human: Callable[[str], TestClient], plugin: Callable[[TestClient, str], Plugin]) -> Setup:
    """Build the Team.

    Args:
        human: Factory of logged-in web clients.
        plugin: Factory of plugin installations.
    """
    alice = human("alice")
    bob = human("bob")
    team_id = alice.post("/api/teams", json={"name": "Acme"}).json()["id"]
    url = alice.post(f"/api/teams/{team_id}/invites").json()["url"]
    token = url.rsplit("/", 1)[1]
    assert bob.post(f"/api/invites/{token}/accept").json()["role"] == "member"
    area_id = alice.post(
        f"/api/teams/{team_id}/areas", json={"name": "Contracts", "description": "API contracts"}
    ).json()["id"]
    return Setup(
        alice=alice,
        bob=bob,
        alice_api=plugin(alice, "billing-api"),
        bob_web=plugin(bob, "web"),
        team_id=team_id,
        area_id=area_id,
    )


def _open(setup: Setup, to: str | None = None) -> dict:
    """Open a Topic by Alice's Assistant.

    Args:
        setup: The Team.
        to: Addressee of the first Message.
    """
    response = setup.alice_api.client.post(
        f"/api/areas/{setup.area_id}/topics",
        json={"title": "Rename field amount", "body": "Can we rename it?", "to": to},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_invite_works_once(setup: Setup, human: Callable[[str], TestClient]) -> None:
    """A used invitation link does not let anyone else in.

    Args:
        setup: The Team.
        human: Factory of logged-in web clients.
    """
    url = setup.alice.post(f"/api/teams/{setup.team_id}/invites").json()["url"]
    token = url.rsplit("/", 1)[1]
    carol, dave = human("carol"), human("dave")

    assert carol.post(f"/api/invites/{token}/accept").status_code == 200
    assert dave.get(f"/api/invites/{token}").json()["valid"] is False
    assert dave.post(f"/api/invites/{token}/accept").status_code == 410
    assert dave.get(f"/api/teams/{setup.team_id}").status_code == 404


def test_only_owner_configures(setup: Setup) -> None:
    """A member cannot create Areas or invite.

    Args:
        setup: The Team.
    """
    assert (
        setup.bob.post(f"/api/teams/{setup.team_id}/areas", json={"name": "X"}).status_code == 403
    )
    assert setup.bob.post(f"/api/teams/{setup.team_id}/invites").status_code == 403


def test_team_shows_members_and_assistants(setup: Setup) -> None:
    """The Team lists its Members with their Assistants and its Areas.

    Args:
        setup: The Team.
    """
    team = setup.bob_web.client.get(f"/api/teams/{setup.team_id}").json()

    assert [(m["pseudonym"], m["role"]) for m in team["members"]] == [
        ("alice", "owner"),
        ("bob", "member"),
    ]
    assert [a["name"] for a in team["members"][0]["assistants"]] == ["alice · billing-api"]
    assert team["areas"][0]["name"] == "Contracts"


def test_topic_opened_by_assistant_is_held_by_it(setup: Setup) -> None:
    """The opening Assistant holds the Topic; the first Message is number 1.

    Args:
        setup: The Team.
    """
    topic = _open(setup)

    assert topic["ref"] == f"T-{topic['id']}"
    assert topic["holder"] == "alice · billing-api"
    assert topic["last_number"] == 1
    assert topic["turns_since_human"] == 0
    assert topic["messages"][0]["assistant"] == "alice · billing-api"


def test_addressed_topic_lands_in_inbox_until_read(setup: Setup) -> None:
    """A Topic addressed to bob is in his Inbox until he reads it through.

    Args:
        setup: The Team.
    """
    topic = _open(setup, to="bob")
    bob = setup.bob_web.client

    (entry,) = bob.get("/api/inbox").json()
    assert (entry["id"], entry["unread"], entry["addressed"]) == (topic["id"], 1, True)
    bob.post(f"/api/topics/{topic['id']}/read", json={"number": 1})
    assert bob.get("/api/inbox").json() == []


def test_reply_with_taken_number_returns_unread(setup: Setup) -> None:
    """A Message with a number that is not next is refused with what was missed (0007).

    Args:
        setup: The Team.
    """
    topic = _open(setup)
    bob = setup.bob_web.client
    first = bob.post(
        f"/api/topics/{topic['id']}/messages", json={"number": 2, "body": "Yes", "to": "alice"}
    )
    assert first.status_code == 201, first.text

    late = setup.alice_api.client.post(
        f"/api/topics/{topic['id']}/messages", json={"number": 2, "body": "Also..."}
    )

    assert late.status_code == 409
    detail = late.json()["detail"]
    assert (detail["code"], detail["next_number"]) == ("number_taken", 3)
    assert [m["body"] for m in detail["unread"]] == ["Yes"]
    assert detail["unread"][0]["to"] == "alice"


def test_reply_points_to_an_earlier_message(setup: Setup) -> None:
    """A reply names an earlier Message of the Topic; itself or a later one is refused.

    Args:
        setup: The Team.
    """
    tid = _open(setup)["id"]
    bob = setup.bob_web.client

    reply = bob.post(
        f"/api/topics/{tid}/messages", json={"number": 2, "body": "Yes", "reply_to": 1}
    )
    to_itself = bob.post(
        f"/api/topics/{tid}/messages", json={"number": 3, "body": "?", "reply_to": 3}
    )
    to_none = bob.post(
        f"/api/topics/{tid}/messages", json={"number": 3, "body": "?", "reply_to": 0}
    )
    topic = setup.alice.get(f"/api/topics/{tid}").json()

    assert reply.status_code == 201, reply.text
    assert reply.json()["reply_to"] == 1
    assert to_itself.status_code == 422
    assert to_none.status_code == 422
    assert [m["reply_to"] for m in topic["messages"]] == [None, 1]


def test_messages_of_the_holder_are_marked(setup: Setup) -> None:
    """A Message is marked when its Assistant held the Topic then; the mark stays after a hold.

    Args:
        setup: The Team.
    """
    tid = _open(setup)["id"]
    alice, bob = setup.alice_api.client, setup.bob_web.client
    bob.post(f"/api/topics/{tid}/messages", json={"number": 2, "body": "Before"})
    bob.post(f"/api/topics/{tid}/hold")
    bob.post(f"/api/topics/{tid}/messages", json={"number": 3, "body": "Holding"})
    alice.post(f"/api/topics/{tid}/messages", json={"number": 4, "body": "Not any more"})
    setup.alice.post(f"/api/topics/{tid}/messages", json={"number": 5, "body": "Human"})

    messages = setup.alice.get(f"/api/topics/{tid}").json()["messages"]

    assert [m["by_holder"] for m in messages] == [True, False, True, False, False]
    assert [m["assistant_id"] for m in messages] == [
        setup.alice_api.assistant_id,
        setup.bob_web.assistant_id,
        setup.bob_web.assistant_id,
        setup.alice_api.assistant_id,
        None,
    ]


def test_migration_marks_messages_of_the_current_holder(setup: Setup, settings: Settings) -> None:
    """Messages written before the mark existed get it when their Assistant holds the Topic now.

    Args:
        setup: The Team.
        settings: Instance settings.
    """
    tid = _open(setup)["id"]
    setup.bob_web.client.post(f"/api/topics/{tid}/messages", json={"number": 2, "body": "Hi"})
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
    command.downgrade(config, "0004")

    migrate(settings.database_url, settings.files_dir)
    messages = setup.alice.get(f"/api/topics/{tid}").json()["messages"]

    assert [m["by_holder"] for m in messages] == [True, False]


def test_unknown_addressee_lists_names(setup: Setup) -> None:
    """Addressing nobody in the Team is refused with the names that work.

    Args:
        setup: The Team.
    """
    topic = _open(setup)

    response = setup.bob_web.client.post(
        f"/api/topics/{topic['id']}/messages", json={"number": 2, "body": "Hi", "to": "carol"}
    )

    assert response.status_code == 422
    assert "alice · billing-api" in response.json()["detail"]


def test_message_to_an_assistant_by_name(setup: Setup) -> None:
    """A Message can be addressed to a specific Assistant.

    Args:
        setup: The Team.
    """
    topic = _open(setup)

    response = setup.bob_web.client.post(
        f"/api/topics/{topic['id']}/messages",
        json={"number": 2, "body": "Hi", "to": "alice · billing-api"},
    )

    assert (response.json()["to"], response.json()["to_assistant"]) == (
        "alice",
        "alice · billing-api",
    )


def test_turn_limit_waits_for_a_human(setup: Setup) -> None:
    """At the limit Assistants' turns are refused until a human writes (decision 0007).

    Args:
        setup: The Team.
    """
    setup.alice.patch(f"/api/teams/{setup.team_id}", json={"turn_limit": 2})
    topic = _open(setup)
    tid = topic["id"]
    alice, bob = setup.alice_api.client, setup.bob_web.client

    assert (
        bob.post(f"/api/topics/{tid}/messages", json={"number": 2, "body": "a"}).status_code == 201
    )
    assert (
        alice.post(f"/api/topics/{tid}/messages", json={"number": 3, "body": "b"}).status_code
        == 201
    )
    blocked = bob.post(f"/api/topics/{tid}/messages", json={"number": 4, "body": "c"})
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "turn_limit"
    progress = alice.post(
        f"/api/topics/{tid}/messages", json={"number": 4, "body": "working", "kind": "progress"}
    )
    assert progress.status_code == 201
    assert (
        setup.bob.post(
            f"/api/topics/{tid}/messages", json={"number": 5, "body": "go on"}
        ).status_code
        == 201
    )
    assert (
        bob.post(f"/api/topics/{tid}/messages", json={"number": 6, "body": "c"}).status_code == 201
    )


def test_relayed_human_words_reset_the_turns(setup: Setup) -> None:
    """An Assistant posting its human's words with ``as_human`` resets the count.

    Args:
        setup: The Team.
    """
    setup.alice.patch(f"/api/teams/{setup.team_id}", json={"turn_limit": 1})
    tid = _open(setup)["id"]
    bob = setup.bob_web.client
    bob.post(f"/api/topics/{tid}/messages", json={"number": 2, "body": "a"})

    relayed = bob.post(
        f"/api/topics/{tid}/messages", json={"number": 3, "body": "Bob says: go", "as_human": True}
    )

    assert relayed.status_code == 201
    assert relayed.json()["relayed"] is True
    assert bob.get(f"/api/topics/{tid}").json()["turns_since_human"] == 0


def test_human_closes_and_assistant_message_reopens(setup: Setup) -> None:
    """Only a human closes a Topic; a new turn in it reopens it.

    Args:
        setup: The Team.
    """
    tid = _open(setup)["id"]
    closing = {"status": "closed", "outcome": "Renamed in ACME-42"}

    assert setup.alice_api.client.patch(f"/api/topics/{tid}", json=closing).status_code == 403
    assert setup.alice.patch(f"/api/topics/{tid}", json=closing).json()["status"] == "closed"
    setup.bob_web.client.post(f"/api/topics/{tid}/messages", json={"number": 2, "body": "One more"})
    reopened = setup.alice.get(f"/api/topics/{tid}").json()
    assert (reopened["status"], reopened["outcome"]) == ("open", "Renamed in ACME-42")


def test_hold_moves_the_topic_to_another_assistant(setup: Setup) -> None:
    """An Assistant can take over holding a Topic.

    Args:
        setup: The Team.
    """
    tid = _open(setup)["id"]

    held = setup.bob_web.client.post(f"/api/topics/{tid}/hold").json()

    assert held["holder"] == "bob · web"


def test_outsider_sees_nothing(
    setup: Setup, human: Callable[[str], TestClient], plugin: Callable[[TestClient, str], Plugin]
) -> None:
    """A User outside the Team gets 404 for its Topics and files.

    Args:
        setup: The Team.
        human: Factory of logged-in web clients.
        plugin: Factory of plugin installations.
    """
    tid = _open(setup)["id"]
    eve = plugin(human("eve"), "x").client

    assert eve.get(f"/api/topics/{tid}").status_code == 404
    assert (
        eve.post(f"/api/topics/{tid}/messages", json={"number": 2, "body": "hi"}).status_code == 404
    )
    assert eve.get(f"/api/teams/{setup.team_id}/topics").status_code == 404


def test_file_upload_attach_download(setup: Setup) -> None:
    """A file is uploaded, attached to a Message and downloaded by a colleague.

    Args:
        setup: The Team.
    """
    tid = _open(setup)["id"]
    alice = setup.alice_api.client
    uploaded = alice.post(
        f"/api/topics/{tid}/files",
        content=b"select 1;\n",
        headers={"X-File-Name": "query%20one.sql", "Content-Type": "text/plain"},
    )
    assert uploaded.status_code == 201, uploaded.text
    file = uploaded.json()

    message = alice.post(
        f"/api/topics/{tid}/messages",
        json={"number": 2, "body": "The script", "file_ids": [file["id"]]},
    ).json()
    download = setup.bob_web.client.get(f"/api/files/{file['id']}")

    assert file["name"] == "query one.sql"
    assert message["files"][0]["id"] == file["id"]
    assert download.content == b"select 1;\n"
    assert "attachment" in download.headers["content-disposition"]
    assert download.headers["content-type"] == "application/octet-stream"
    assert "sandbox" in download.headers["content-security-policy"]
    assert not file["preview"]


PNG = b"\x89PNG\r\n\x1a\n" + bytes(24)


def _upload(client: TestClient, topic_id: int, name: str, content: bytes, kind: str) -> dict:
    """Upload a file into a Topic.

    Args:
        client: The uploader.
        topic_id: The Topic.
        name: File name.
        content: The content.
        kind: The media type the uploader declares.
    """
    response = client.post(
        f"/api/topics/{topic_id}/files",
        content=content,
        headers={"X-File-Name": name, "Content-Type": kind},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_image_is_shown_inline(setup: Setup) -> None:
    """A PNG declared as opaque bytes, as the plugin uploads it, is served inline as an image.

    Args:
        setup: The Team.
    """
    tid = _open(setup)["id"]
    file = _upload(setup.alice_api.client, tid, "shot.png", PNG, "application/octet-stream")

    shown = setup.bob.get(f"/api/files/{file['id']}")
    saved = setup.bob.get(f"/api/files/{file['id']}", params={"download": 1})

    assert file["preview"]
    assert shown.headers["content-type"] == "image/png"
    assert shown.headers["content-disposition"].startswith("inline")
    assert "sandbox" in shown.headers["content-security-policy"]
    assert shown.headers["x-content-type-options"] == "nosniff"
    assert shown.content == PNG
    assert saved.headers["content-type"] == "application/octet-stream"
    assert saved.headers["content-disposition"].startswith("attachment")


@pytest.mark.parametrize(
    ("name", "content", "kind"),
    [
        ("chart.svg", b'<svg xmlns="http://www.w3.org/2000/svg"><script/></svg>', "image/svg+xml"),
        ("fake.png", b"<html><script>alert(1)</script></html>", "image/png"),
    ],
)
def test_non_raster_file_is_only_downloaded(
    setup: Setup, name: str, content: bytes, kind: str
) -> None:
    """An SVG, or a page declared as a PNG, is not shown: its content is not a raster image.

    Args:
        setup: The Team.
        name: File name.
        content: The content.
        kind: The media type the uploader declares.
    """
    tid = _open(setup)["id"]
    file = _upload(setup.alice, tid, name, content, kind)

    download = setup.bob.get(f"/api/files/{file['id']}")

    assert not file["preview"]
    assert download.headers["content-type"] == "application/octet-stream"
    assert download.headers["content-disposition"].startswith("attachment")
    assert download.headers["x-content-type-options"] == "nosniff"


def test_signature_across_chunks(setup: Setup, live_url: str) -> None:
    """The first bytes are collected from the first chunks of a body; later ones do not count.

    The test client sends a body in one piece, so the upload goes to uvicorn in three chunks
    with pauses between them.

    Args:
        setup: The Team.
        live_url: Address of the same application served by uvicorn.
    """
    tid = _open(setup)["id"]
    headers = {
        "Authorization": setup.alice_api.client.headers["Authorization"],
        "X-File-Name": "shot.png",
    }

    def body() -> Iterator[bytes]:
        """Yield a PNG cut inside its signature, then bytes that are no image."""
        for chunk in (PNG[:3], PNG[3:], bytes(16)):
            yield chunk
            time.sleep(0.05)

    with httpx.Client(base_url=live_url, timeout=10) as client:
        response = client.post(f"/api/topics/{tid}/files", content=body(), headers=headers)

    assert response.status_code == 201, response.text
    assert response.json()["preview"]


def test_large_image_is_not_previewed(setup: Setup) -> None:
    """An image over the preview limit is listed as an ordinary file but still served inline.

    Args:
        setup: The Team; the test settings preview images up to 512 bytes.
    """
    tid = _open(setup)["id"]
    file = _upload(setup.alice, tid, "big.png", PNG + bytes(600), "image/png")

    topic = setup.bob.get(f"/api/topics/{tid}").json()

    assert not file["preview"]
    assert not topic["files"][0]["preview"]
    assert setup.bob.get(f"/api/files/{file['id']}").headers["content-type"] == "image/png"


def test_migration_recognises_earlier_images(setup: Setup, settings: Settings) -> None:
    """Files uploaded before the image type was kept get it from their content on disk.

    Args:
        setup: The Team.
        settings: Instance settings.
    """
    tid = _open(setup)["id"]
    image = _upload(setup.alice_api.client, tid, "shot.png", PNG, "application/octet-stream")
    text = _upload(setup.alice_api.client, tid, "notes.txt", b"notes", "text/plain")
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
    command.downgrade(config, "0002")

    migrate(settings.database_url, settings.files_dir)
    files = {f["id"]: f for f in setup.bob.get(f"/api/topics/{tid}").json()["files"]}

    assert files[image["id"]]["preview"]
    assert not files[text["id"]]["preview"]


def test_file_limits(setup: Setup) -> None:
    """Files over the size limit or over the Team's storage are refused.

    Args:
        setup: The Team; the test settings allow 1 KB per file and 4 KB per Team.
    """
    tid = _open(setup)["id"]
    alice = setup.alice_api.client
    headers = {"X-File-Name": "f.bin"}

    assert (
        alice.post(f"/api/topics/{tid}/files", content=b"x" * 2000, headers=headers).status_code
        == 413
    )
    for _ in range(4):
        assert (
            alice.post(f"/api/topics/{tid}/files", content=b"x" * 1000, headers=headers).status_code
            == 201
        )
    assert (
        alice.post(f"/api/topics/{tid}/files", content=b"x" * 200, headers=headers).status_code
        == 413
    )


def test_file_of_another_topic_cannot_be_attached(setup: Setup) -> None:
    """Attaching a file uploaded to another Topic is refused.

    Args:
        setup: The Team.
    """
    first, second = _open(setup)["id"], _open(setup)["id"]
    alice = setup.alice_api.client
    file_id = alice.post(
        f"/api/topics/{first}/files", content=b"a", headers={"X-File-Name": "a.txt"}
    ).json()["id"]

    response = alice.post(
        f"/api/topics/{second}/messages", json={"number": 2, "body": "x", "file_ids": [file_id]}
    )

    assert response.status_code == 422


def test_events_reach_every_member(setup: Setup, live_url: str) -> None:
    """A Message makes an event for a Member's stream, which starts after the given id.

    Args:
        setup: The Team.
        live_url: Address of the same application served by uvicorn.
    """
    tid = _open(setup, to="bob")["id"]
    headers = {"Authorization": setup.bob_web.client.headers["Authorization"]}

    frames = []
    with (
        httpx.Client(base_url=live_url, headers=headers, timeout=10) as client,
        client.stream("GET", "/api/events?after=0") as stream,
    ):
        for line in stream.iter_lines():
            frames.append(line)
            if line.startswith("data:") and "event: message" in frames:
                break

    assert "event: ready" in frames
    assert "event: topic" in frames
    data = next(f for f in frames[frames.index("event: message") :] if f.startswith("data:"))
    assert f'"topic_id": {tid}' in data
    assert '"to_user_id"' in data


def test_stream_wakes_on_new_message(setup: Setup, live_url: str) -> None:
    """A Message posted while the stream waits reaches it at once.

    Args:
        setup: The Team.
        live_url: Address of the same application served by uvicorn.
    """
    tid = _open(setup)["id"]
    headers = {"Authorization": setup.bob_web.client.headers["Authorization"]}

    with (
        httpx.Client(base_url=live_url, headers=headers, timeout=10) as client,
        client.stream("GET", "/api/events") as stream,
    ):
        lines = (line for line in stream.iter_lines() if line)
        assert next(lines) == "retry: 3000"
        assert next(lines) == "event: ready"
        assert next(lines).startswith("data: ")
        with httpx.Client(base_url=live_url, headers=headers) as writer:
            posted = writer.post(f"/api/topics/{tid}/messages", json={"number": 2, "body": "hi"})
            assert posted.status_code == 201
        frame = [next(lines) for _ in range(3)]

    assert frame[0].startswith("id: ")
    assert frame[1] == "event: message"
