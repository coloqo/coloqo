"""Tests of quiet work: idle free Topics close, quiet tasks are noticed, nothing is deleted
(decisions 0021, 0030, 0032)."""

import asyncio
from datetime import timedelta

from coloqo_server import retention
from coloqo_server.db import Database
from coloqo_server.security import now
from coloqo_server.settings import Settings
from tests.conftest import Setup, _connect
from tests.test_topics import _open

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


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


def _open_free(setup: Setup, to: str | None = None) -> int:
    """Open a free Topic by Alice's Assistant, as a plugin that knows tasks; return its number.

    Args:
        setup: The Team.
        to: Addressee of the first Message.
    """
    response = setup.alice_api.client.post(
        f"/api/team/{setup.team}/topic",
        json={"area": setup.area, "title": "Q", "body": "Hi", "to": to, "free": True},
        headers={"X-Coloqo-Plugin": "0.7.0"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["ref"].startswith("F-")
    return response.json()["number"]


def _age(settings: Settings, number: int, column: str, days: float) -> None:
    """Move a free Topic's time back, as if that much time had passed.

    Args:
        settings: Instance settings.
        number: The free Topic's number; the tests have one Team.
        column: ``updated_at`` or ``closed_at``.
        days: How far back.
    """
    with _connect(settings.database_url) as connection:
        connection.execute(
            f"UPDATE topics SET {column} = now() - %s WHERE number = %s",
            (timedelta(days=days), number),
        )


def _age_task(settings: Settings, number: int, days: float, noticed: float | None = None) -> None:
    """Move a task's activity, and its Topic's, back, as if that much time had passed.

    Args:
        settings: Instance settings.
        number: The task's number; the tests have one Team.
        days: How far back its last activity goes.
        noticed: How long ago its assignee was last told; ``None`` for never.
    """
    with _connect(settings.database_url) as connection:
        connection.execute(
            "UPDATE tasks SET updated_at = now() - %s, idle_noticed_at = %s WHERE number = %s",
            (timedelta(days=days), now() - timedelta(days=noticed) if noticed else None, number),
        )
        connection.execute(
            "UPDATE topics SET updated_at = now() - %s FROM tasks "
            "WHERE tasks.id = topics.task_id AND tasks.number = %s",
            (timedelta(days=days), number),
        )


def _events(settings: Settings, kind: str) -> list[dict]:
    """Return the data of the stored events of a kind, oldest first.

    Args:
        settings: Instance settings.
        kind: The event kind.
    """
    with _connect(settings.database_url) as connection:
        return [
            row[0]
            for row in connection.execute(
                "SELECT data FROM events WHERE kind = %s ORDER BY id", (kind,)
            ).fetchall()
        ]


def test_idle_topic_is_announced_once(setup: Setup, settings: Settings) -> None:
    """Three days before closing, the Team is told once (decision 0028).

    Args:
        setup: The Team.
        settings: Instance settings.
    """
    number = _open_free(setup, to="bob")
    _age(settings, number, "updated_at", 28)

    first, second = _tend(settings), _tend(settings)
    topic = setup.alice.get(f"/api/team/{setup.team}/topic/{number}").json()
    (data,) = _events(settings, "topic_idle")

    assert len(first) == 2
    assert second == set()
    assert topic["status"] == "open"
    assert (data["holder"], data["holder_live"]) == (setup.alice_api.key, True)
    assert data["holder_project"] == setup.alice_api.project_key
    assert (data["topic_kind"], data["ref"]) == ("free", f"F-{number}")


def test_idle_topic_closes_with_a_line(setup: Setup, settings: Settings) -> None:
    """After 30 quiet days a free Topic is closed by Coloqo, with the outcome in its feed.

    Args:
        setup: The Team.
        settings: Instance settings.
    """
    number = _open_free(setup)
    _age(settings, number, "updated_at", 31)

    told = _tend(settings)
    topic = setup.alice.get(f"/api/team/{setup.team}/topic/{number}").json()
    line = topic["messages"][-1]

    assert topic["status"] == "closed"
    assert topic["outcome"].startswith("Closed for inactivity")
    assert topic["deletes_at"] is None
    assert (line["kind"], line["system"], line["assistant"]) == ("closed", True, None)
    assert len(told) == 2


def test_closed_topics_are_kept(setup: Setup, settings: Settings) -> None:
    """A Topic closed long ago keeps its conversation and files (decision 0030).

    Args:
        setup: The Team.
        settings: Instance settings.
    """
    number = _open_free(setup)
    file = setup.alice.post(
        f"/api/team/{setup.team}/topic/{number}/file",
        content=PNG,
        headers={"X-File-Name": "shot.png", "Content-Type": "image/png"},
    )
    assert file.status_code == 201, file.text
    setup.alice.patch(
        f"/api/team/{setup.team}/topic/{number}", json={"status": "closed", "outcome": "Done"}
    )
    _age(settings, number, "closed_at", 400)

    _tend(settings)
    topic = setup.alice.get(f"/api/team/{setup.team}/topic/{number}").json()

    assert topic["deleted_at"] is None
    assert len(topic["messages"]) == 2
    assert [f["name"] for f in topic["files"]] == ["shot.png"]
    assert (
        setup.alice.get(f"/api/team/{setup.team}/file/{file.json()['number']}").status_code == 200
    )


def test_a_task_s_topic_never_closes_for_inactivity(setup: Setup, settings: Settings) -> None:
    """A quiet task is noticed, never closed: that would write a false outcome (decision 0032).

    Args:
        setup: The Team.
        settings: Instance settings.
    """
    number = _open(setup)["number"]
    _age_task(settings, number, 40)

    _tend(settings)
    topic = setup.alice.get(f"/api/team/{setup.team}/task/{number}/topic").json()

    assert topic["status"] == "open"
    assert _events(settings, "topic_idle") == []
    assert [e["ref"] for e in _events(settings, "task_idle")] == [f"T-{number}"]


def test_a_quiet_task_is_noticed_every_day(setup: Setup, settings: Settings) -> None:
    """After 7 quiet days its assignee is told, then again every day while it stays quiet.

    Args:
        setup: The Team.
        settings: Instance settings.
    """
    number = _open(setup)["number"]
    _age_task(settings, number, 6)
    _tend(settings)
    early = _events(settings, "task_idle")

    _age_task(settings, number, 8)
    _tend(settings)
    _tend(settings)
    once = _events(settings, "task_idle")

    _age_task(settings, number, 9, noticed=1.1)
    _tend(settings)
    (first, second) = _events(settings, "task_idle")

    assert early == []
    assert len(once) == 1
    assert (first["task"], first["stage"], first["assignee"]) == (number, "Analysis", "alice")
    assert second["days"] == 9


def test_a_waiting_task_is_not_quiet(setup: Setup, settings: Settings) -> None:
    """A task marked as waiting for something outside the Team gets no notice (decision 0032).

    Args:
        setup: The Team.
        settings: Instance settings.
    """
    number = _open(setup)["number"]
    waited = setup.alice_api.client.post(
        f"/api/team/{setup.team}/task/{number}/wait", json={"what": "a token from infra"}
    )
    assert waited.status_code == 200, waited.text
    _age_task(settings, number, 30)

    _tend(settings)

    assert _events(settings, "task_idle") == []


def test_the_team_sets_the_quiet_days(setup: Setup, settings: Settings) -> None:
    """The threshold and the repetition are the Team's settings.

    Args:
        setup: The Team.
        settings: Instance settings.
    """
    number = _open(setup)["number"]
    changed = setup.alice.patch(
        f"/api/team/{setup.team}", json={"task_idle_days": 14, "task_idle_repeat_days": 3}
    )
    _age_task(settings, number, 10)
    _tend(settings)
    before = _events(settings, "task_idle")
    _age_task(settings, number, 15, noticed=2)
    _tend(settings)
    still = _events(settings, "task_idle")
    _age_task(settings, number, 16, noticed=3.1)
    _tend(settings)

    assert (changed.json()["task_idle_days"], changed.json()["task_idle_repeat_days"]) == (14, 3)
    assert before == still == []
    assert len(_events(settings, "task_idle")) == 1
