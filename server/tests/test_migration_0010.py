"""Test of migration 0010 on Topics made before it: each becomes a task with its number (0031)."""

from collections.abc import Callable

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from coloqo_server.db import MIGRATIONS_DIR, migrate
from coloqo_server.settings import Settings
from tests.conftest import Plugin, _connect


def _down(settings: Settings) -> None:
    """Bring the database down to 0009.

    Args:
        settings: Instance settings.
    """
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
    command.downgrade(config, "0009")


def test_every_topic_becomes_a_task_with_its_number(
    settings: Settings, human: Callable[[str], TestClient], plugin: Callable[..., Plugin]
) -> None:
    """Open Topics land in analysis, closed ones done; issues become links; old links and old
    plugins resolve to the tasks; both counters continue after them.

    Args:
        settings: Instance settings.
        human: Factory of logged-in web clients.
        plugin: Factory of plugin installations.
    """
    alice, bob = human("alice"), human("bob")
    alice.post("/api/team", json={"name": "Acme"})
    alice.post("/api/team/acme/area", json={"name": "Dev"})
    invite = alice.post("/api/team/acme/invite").json()["url"].rsplit("/", 1)[1]
    bob.post(f"/api/invite/{invite}/accept")
    old = plugin(bob, "web", "acme")
    _down(settings)
    with _connect(settings.database_url) as db:
        ((alice_id,),) = db.execute("SELECT id FROM users WHERE pseudonym = 'alice'").fetchall()
        ((holder,),) = db.execute("SELECT id FROM assistants").fetchall()
        ((team,),) = db.execute("SELECT id FROM teams").fetchall()
        ((area,),) = db.execute("SELECT id FROM areas").fetchall()
        for number, status, issue, holder_id, closed in (
            (1, "open", "", holder, None),
            (2, "closed", "ACME-42", None, "now() - interval '3 days'"),
            (3, "closed", "https://tracker.example/ACME-7", None, "now() - interval '1 day'"),
        ):
            db.execute(
                "INSERT INTO topics (team_id, number, area_id, title, issue, status, outcome, "
                "created_by, holder_assistant_id, last_number, turns_since_human, closed_at) "
                f"VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 1, 0, {closed or 'NULL'})",
                (
                    team,
                    number,
                    area,
                    f"Topic {number}",
                    issue,
                    status,
                    "Merged" if closed else "",
                    alice_id,
                    holder_id,
                ),
            )
            db.execute(
                "INSERT INTO messages (topic_id, number, kind, author_user_id, body) "
                "SELECT id, 1, 'message', %s, 'Hi' FROM topics WHERE number = %s",
                (alice_id, number),
            )
        db.execute("UPDATE teams SET last_topic = 3")

    migrate(settings.database_url, settings.files_dir)
    tasks = {t["number"]: t for t in alice.get("/api/team/acme/task").json()}
    first = alice.get("/api/team/acme/task/1").json()
    by_old_link = alice.get("/api/team/acme/topic/2").json()
    by_old_plugin = old.client.get("/api/team/acme/topic/3").json()
    workflows = alice.get("/api/team/acme/workflow").json()
    alice.patch("/api/team/acme", json={"tracker": True})
    new_task = alice.post("/api/team/acme/task", json={"area": "dev", "title": "New"}).json()
    new_free = alice.post(
        "/api/team/acme/topic", json={"area": "dev", "title": "Q", "body": "?", "free": True}
    ).json()

    assert {n: (t["stage"], t["assignee"]) for n, t in tasks.items()} == {
        1: ("Analysis", "bob"),
        2: ("Done", "alice"),
        3: ("Done", "alice"),
    }
    assert tasks[2]["links"] == [{"key": "ACME-42", "url": ""}]
    assert tasks[3]["links"][0]["url"] == "https://tracker.example/ACME-7"
    assert tasks[2]["finished_at"] is not None and tasks[1]["finished_at"] is None
    assert [(e["kind"], e["data"].get("migrated")) for e in first["timeline"]] == [
        ("created", True),
        ("stage", True),
    ]
    assert first["topic"]["messages"][0]["body"] == "Hi"
    assert (by_old_link["ref"], by_old_link["kind"], by_old_link["outcome"]) == (
        "T-2",
        "task",
        "Merged",
    )
    assert by_old_plugin["ref"] == "T-3"
    assert workflows[0]["areas"] == ["dev"]
    assert new_task["ref"] == "T-4"
    assert new_free["ref"] == "F-4"
