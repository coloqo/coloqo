"""Tests of how long a Topic lives: idle notice, closing for inactivity, deletion (0021)."""

import asyncio
from datetime import timedelta
from pathlib import Path

from coloqo_server import retention
from coloqo_server.db import Database
from coloqo_server.security import now
from coloqo_server.settings import Settings
from tests.conftest import Setup, _connect
from tests.test_topics import PNG, _open, _upload


def _tend(settings: Settings) -> set[int]:
    """Run the life cycle once, as the hourly cleanup does.

    Args:
        settings: Instance settings.
    """

    async def run() -> set[int]:
        """Tend the Topics in a session of its own."""
        database = Database(settings.database_url)
        try:
            async with database.sessions() as db:
                return await retention.tend(db, settings, now())
        finally:
            await database.dispose()

    return asyncio.run(run())


def _age(settings: Settings, topic_id: int, column: str, days: float) -> None:
    """Move a Topic's time back, as if that much time had passed.

    Args:
        settings: Instance settings.
        topic_id: The Topic.
        column: ``updated_at`` or ``closed_at``.
        days: How far back.
    """
    with _connect(settings.database_url) as connection:
        connection.execute(
            f"UPDATE topics SET {column} = now() - %s WHERE id = %s",
            (timedelta(days=days), topic_id),
        )


def test_idle_topic_is_announced_once(setup: Setup, settings: Settings) -> None:
    """Three days before closing, the holder's and the participants' people are told, once.

    Args:
        setup: The Team.
        settings: Instance settings.
    """
    tid = _open(setup, to="bob")["id"]
    _age(settings, tid, "updated_at", 28)

    first, second = _tend(settings), _tend(settings)
    topic = setup.alice.get(f"/api/topics/{tid}").json()

    assert len(first) == 2
    assert second == set()
    assert topic["status"] == "open"


def test_idle_topic_closes_with_a_line(setup: Setup, settings: Settings) -> None:
    """After 30 quiet days a Topic is closed by Coloqo, with the outcome in its feed.

    Args:
        setup: The Team.
        settings: Instance settings.
    """
    tid = _open(setup)["id"]
    _age(settings, tid, "updated_at", 31)

    told = _tend(settings)
    topic = setup.alice.get(f"/api/topics/{tid}").json()
    line = topic["messages"][-1]

    assert topic["status"] == "closed"
    assert topic["outcome"].startswith("Closed for inactivity")
    assert topic["deletes_at"] is not None
    assert (line["kind"], line["system"], line["assistant"]) == ("closed", True, None)
    assert len(told) == 2


def test_archive_keeps_the_card_and_drops_the_rest(setup: Setup, settings: Settings) -> None:
    """After the archive time the conversation and files go; the Topic stays as a card.

    Args:
        setup: The Team.
        settings: Instance settings.
    """
    tid = _open(setup)["id"]
    file = _upload(setup.alice_api.client, tid, "shot.png", PNG, "image/png")
    setup.alice_api.client.patch(
        f"/api/topics/{tid}", json={"status": "closed", "outcome": "Done in ACME-42"}
    )
    path = Path(settings.files_dir) / str(setup.team_id) / str(file["id"])
    _age(settings, tid, "closed_at", 8)

    _tend(settings)
    card = setup.alice.get(f"/api/topics/{tid}").json()
    listed = setup.alice.get(f"/api/teams/{setup.team_id}/topics").json()
    write = setup.bob_web.client.post(
        f"/api/topics/{tid}/messages", json={"number": 9, "body": "x"}
    )

    assert (card["title"], card["outcome"]) == ("Rename field amount", "Done in ACME-42")
    assert card["deleted_at"] is not None
    assert (card["messages"], card["files"]) == ([], [])
    assert not path.exists()
    assert setup.alice.get(f"/api/files/{file['id']}").status_code == 404
    assert tid not in [t["id"] for t in listed]
    assert write.status_code == 410


def test_team_keeps_its_own_archive_time(setup: Setup, settings: Settings) -> None:
    """A Team with a longer archive keeps a Topic the instance's default would delete.

    Args:
        setup: The Team.
        settings: Instance settings.
    """
    tid = _open(setup)["id"]
    setup.alice.patch(f"/api/topics/{tid}", json={"status": "closed"})
    with _connect(settings.database_url) as connection:
        connection.execute("UPDATE teams SET archive_days = 30 WHERE id = %s", (setup.team_id,))
    _age(settings, tid, "closed_at", 8)

    _tend(settings)
    topic = setup.alice.get(f"/api/topics/{tid}").json()

    assert topic["deleted_at"] is None
    assert len(topic["messages"]) == 2
