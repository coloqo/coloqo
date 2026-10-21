"""Tests of events numbered per Team and the stream's cursor (decision 0028)."""

from collections.abc import Iterator

import httpx
import pytest
from fastapi.testclient import TestClient

from coloqo_server.api.stream import read_cursor, write_cursor
from coloqo_server.settings import Settings
from tests.conftest import Two, _connect
from tests.test_links import _topic


def test_cursor_names_a_number_per_team() -> None:
    """A cursor is read by slug, other parts left out, and written in the slugs' order."""
    assert read_cursor("globex:12, acme:3,7,x:y,Acme:1,acme-2:0") == {
        "globex": 12,
        "acme": 3,
        "acme-2": 0,
    }
    assert read_cursor(None) == read_cursor("") == {}
    assert write_cursor({2: 12, 1: 3}, {1: "acme", 2: "globex"}) == "acme:3,globex:12"


def test_events_are_numbered_per_team_without_gaps(two: Two, settings: Settings) -> None:
    """Each Team's events take 1, 2, 3...; an event is stored once, not per Member.

    Args:
        two: The Teams.
        settings: Instance settings.
    """
    _topic(two.alice, "acme")
    _topic(two.bob, "globex")
    _topic(two.alice, "acme")

    with _connect(settings.database_url) as connection:
        rows = connection.execute(
            "SELECT t.slug, e.number, t.last_event FROM events e JOIN teams t ON t.id = e.team_id "
            "ORDER BY e.id"
        ).fetchall()

    # A new Topic is a "topic" event and its first Message a "message" one.
    assert [(slug, number) for slug, number, _ in rows] == [
        ("acme", 1),
        ("acme", 2),
        ("globex", 1),
        ("globex", 2),
        ("acme", 3),
        ("acme", 4),
    ]
    assert {slug: last for slug, _, last in rows} == {"acme": 4, "globex": 2}


def _events(url: str, client: TestClient, cursor: str | None, wanted: int) -> Iterator[tuple]:
    """Read a web stream from a cursor and yield ``(id, kind, data)`` of its first frames.

    Args:
        url: The live server.
        client: A logged-in web client, whose cookies the stream uses.
        cursor: What to send as ``Last-Event-ID``; none when omitted.
        wanted: How many frames, ``ready`` included, to read before closing.
    """
    # The test client's cookies belong to its own host name; the live server has another.
    headers = {"Cookie": "; ".join(f"{name}={value}" for name, value in client.cookies.items())}
    if cursor is not None:
        headers["Last-Event-ID"] = cursor
    frame: dict[str, str] = {}
    count = 0
    with (
        httpx.Client(base_url=url, timeout=10) as http,
        http.stream("GET", "/api/events", headers=headers) as stream,
    ):
        assert stream.status_code == 200
        for line in stream.iter_lines():
            if line:
                key, _, value = line.partition(": ")
                frame[key] = value
                continue
            if "event" in frame:
                yield frame.get("id"), frame["event"], frame["data"]
                count += 1
                if count == wanted:
                    return
            frame = {}


@pytest.mark.parametrize(
    ("cursor", "first"),
    [
        ("acme:2,globex:0", ["acme:2,globex:1", "acme:2,globex:2", "acme:3,globex:2"]),
        ("acme:2", ["acme:3,globex:2", "acme:4,globex:2"]),
        ("1234", None),
        ("acme:999,globex:999", None),
    ],
)
def test_stream_resumes_from_the_cursor(
    two: Two,
    live_url: str,
    cursor: str,
    first: list[str] | None,
) -> None:
    """Missed events come after the cursor; a Team it does not name starts at its current number.

    An old database id or numbers past a Team's last are not a cursor to resume from: the
    stream gives new events only, and the next one arrives.

    Args:
        two: The Teams.
        live_url: Address of the same application served by uvicorn.
        cursor: What the client reconnects with.
        first: The ids of the first events it gets; ``None`` for new events only.
    """
    _topic(two.alice, "acme")
    _topic(two.alice, "globex")
    _topic(two.alice, "acme")
    if first is None:
        frames = _events(live_url, two.bob, cursor, 1)
        assert [(kind, data) for _, kind, data in frames] == [
            ("ready", '{"last": "acme:4,globex:2"}')
        ]
        return

    frames = list(_events(live_url, two.bob, cursor, 1 + len(first)))

    assert frames[0][1] == "ready"
    assert [frame_id for frame_id, _, _ in frames[1:]] == first[: len(frames) - 1]


def test_cursor_with_a_former_slug_still_resumes(two: Two, live_url: str) -> None:
    """A Team renamed while a client was away is found by the slug in its cursor.

    Args:
        two: The Teams.
        live_url: Address of the same application served by uvicorn.
    """
    _topic(two.alice, "acme")
    two.alice.patch("/api/team/acme", json={"slug": "acme-inc"})
    _topic(two.alice, "acme-inc")

    frames = list(_events(live_url, two.bob, "acme:2,globex:0", 2))

    assert frames[0] == (None, "ready", '{"last": "acme-inc:2,globex:0"}')
    assert frames[1][0] == "acme-inc:3,globex:0"
