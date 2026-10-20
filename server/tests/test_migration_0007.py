"""Test of migration 0007 on data made before it: nothing of the pilot's is lost (0024-0026)."""

from collections.abc import Callable
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from coloqo_server.db import MIGRATIONS_DIR, migrate
from coloqo_server.naming import WORDS
from coloqo_server.settings import Settings
from tests.conftest import _connect


def _before(settings: Settings) -> None:
    """Bring the database down to 0006 and write a pilot's data in that schema.

    Two Teams, one with a Cyrillic name; an Assistant per project; Topics and files numbered by
    one sequence across the Teams; a relayed Message and an ordinary one.

    Args:
        settings: Instance settings.
    """
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
    command.downgrade(config, "0006")
    with _connect(settings.database_url) as db:
        db.execute("INSERT INTO users (id, pseudonym) VALUES (1, 'alice'), (2, 'bob')")
        db.execute(
            "INSERT INTO teams (id, name, turn_limit) VALUES (1, 'Платёжный сервис', 10), "
            "(2, 'Globex', 10)"
        )
        db.execute(
            "INSERT INTO members (team_id, user_id, role) VALUES (1, 1, 'owner'), "
            "(1, 2, 'member'), (2, 1, 'owner')"
        )
        db.execute(
            "INSERT INTO areas (id, team_id, name, description) VALUES "
            "(1, 1, 'Разработка', ''), (2, 2, 'Dev', '')"
        )
        db.execute(
            "INSERT INTO installations (id, user_id, name, token_hash) VALUES "
            "(1, 1, 'laptop', 'h1'), (2, 2, 'desktop', 'h2')"
        )
        db.execute(
            "INSERT INTO assistants (id, user_id, installation_id, project_key, name, team_id) "
            "VALUES (1, 1, 1, 'k1', 'alice · billing-api', 1), (2, 2, 2, 'k2', 'bob · web', 1)"
        )
        for topic_id, team_id, area_id in ((1, 1, 1), (2, 2, 2), (3, 1, 1)):
            db.execute(
                "INSERT INTO topics (id, team_id, area_id, title, issue, status, outcome, "
                "created_by, holder_assistant_id, last_number, turns_since_human) "
                "VALUES (%s, %s, %s, 'Q', '', 'open', '', 1, 1, 2, 1)",
                (topic_id, team_id, area_id),
            )
            db.execute(
                "INSERT INTO messages (topic_id, number, kind, author_user_id, "
                "author_assistant_id, relayed, body) VALUES "
                "(%s, 1, 'message', 1, 1, false, 'own'), (%s, 2, 'message', 2, 2, true, 'said')",
                (topic_id, topic_id),
            )
        for file_id, topic_id, team_id in ((1, 1, 1), (2, 2, 2), (3, 3, 1)):
            db.execute(
                "INSERT INTO files (id, topic_id, name, size, sha256, content_type, uploaded_by) "
                "VALUES (%s, %s, 'f.txt', 1, 'x', 'text/plain', 1)",
                (file_id, topic_id),
            )
            path = Path(settings.files_dir) / str(team_id) / str(file_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(str(file_id).encode())


def test_migration_keeps_the_pilot_s_data(
    app: object, settings: Settings, human: Callable[[str], TestClient]
) -> None:
    """Slugs from names, per-Team numbers in the old order, sessions, marks, files on disk.

    Args:
        app: The application, migrated and emptied before the test.
        settings: Instance settings.
        human: Factory of logged-in web clients.
    """
    _before(settings)

    migrate(settings.database_url, settings.files_dir)
    alice, bob = human("alice"), human("bob")
    teams = {t["name"]: t for t in alice.get("/api/team").json()}
    pay = teams["Платёжный сервис"]["slug"]
    topics = alice.get(f"/api/team/{pay}/topic").json()
    detail = bob.get(f"/api/team/{pay}/topic/2").json()
    team = alice.get(f"/api/team/{pay}").json()

    assert (pay, teams["Globex"]["slug"]) == ("platyozhnyy-servis", "globex")
    assert team["areas"][0]["slug"] == "razrabotka"
    assert sorted(t["number"] for t in topics) == [1, 2]
    assert alice.get("/api/team/globex/topic/1").json()["number"] == 1
    assert [m["human_part"] for m in detail["messages"]] == [None, "words"]
    holder, word = detail["holder"].rsplit(" · ", 1)
    assert holder == "alice · billing-api"
    assert word in WORDS
    assert [f["number"] for f in detail["files"]] == [2]
    assert alice.get(f"/api/team/{pay}/file/2").content == b"3"
    assert alice.get("/api/team/globex/file/1").content == b"2"
    assert [(p["name"], p["team"]) for p in alice.get("/api/project").json()] == [
        ("billing-api", pay)
    ]
