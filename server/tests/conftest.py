"""Fixtures: a real PostgreSQL database, the application and logged-in clients.

The database comes from ``COLOQO_TEST_DATABASE_URL``; it is created if missing and emptied
before every test.
"""

import hashlib
import os
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

import psycopg
import pytest
import uvicorn
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url

from coloqo_server.app import create_app
from coloqo_server.settings import Settings

TEST_DATABASE_URL = os.environ.get(
    "COLOQO_TEST_DATABASE_URL", "postgresql+psycopg://coloqo:dev@127.0.0.1:55432/coloqo_test"
)
ORIGIN = "https://testserver"


def _connect(url: str, database: str | None = None) -> psycopg.Connection:
    """Open a plain psycopg connection.

    Args:
        url: SQLAlchemy URL.
        database: Another database on the same server.

    Raises:
        psycopg.OperationalError: The server cannot be reached.
    """
    parsed = make_url(url)
    return psycopg.connect(
        host=parsed.host,
        port=parsed.port,
        user=parsed.username,
        password=parsed.password,
        dbname=database or parsed.database,
        autocommit=True,
    )


@pytest.fixture(scope="session")
def database_url() -> str:
    """Create the test database once per run."""
    name = make_url(TEST_DATABASE_URL).database
    with _connect(TEST_DATABASE_URL, "postgres") as connection:
        exists = connection.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (name,)
        ).fetchone()
        if not exists:
            connection.execute(f'CREATE DATABASE "{name}"')
    return TEST_DATABASE_URL


class FakeGitHub:
    """A login provider that accepts code ``id-<n>`` as GitHub user ``n``."""

    name = "github"

    def authorize_url(self, state: str, redirect_uri: str) -> str:
        """Return a fake provider page.

        Args:
            state: The state to bring back.
            redirect_uri: The callback.
        """
        return f"https://github.example/authorize?state={state}"

    async def subject(self, code: str, redirect_uri: str) -> str:
        """Return the id in the code.

        Args:
            code: ``id-<n>``.
            redirect_uri: The callback.
        """
        return code.removeprefix("id-")


@pytest.fixture
def settings(database_url: str, tmp_path: Path) -> Settings:
    """Settings for a test instance.

    Args:
        database_url: The test database.
        tmp_path: Temporary directory for files.
    """
    return Settings(
        web_dir=None,
        database_url=database_url,
        public_url=ORIGIN,
        dev_login=True,
        files_dir=tmp_path / "files",
        max_file_bytes=1024,
        team_storage_bytes=4096,
        preview_max_bytes=512,
    )


@pytest.fixture
def app(settings: Settings) -> Iterator[FastAPI]:
    """The application on an emptied database.

    Args:
        settings: Instance settings.
    """
    application = create_app(settings, providers={"github": FakeGitHub()})
    with TestClient(application, base_url=ORIGIN):
        pass  # runs the migrations
    with _connect(settings.database_url) as connection:
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public' "
                "AND tablename <> 'alembic_version'"
            )
        ]
        connection.execute(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE")
    yield application


@dataclass
class Plugin:
    """A plugin installation acting as one session's Assistant.

    Attributes:
        client: Client sending the installation token, the plugin's version and the
            Assistant's key.
        key: The Assistant's key.
        assistant: Its shown name.
        project_key: Its project's public key.
        word: Its word.
    """

    client: TestClient
    key: str
    assistant: str
    project_key: str
    word: str


@pytest.fixture
def human(app: FastAPI) -> Iterator[Callable[[str], TestClient]]:
    """Make web clients logged in by development login.

    Args:
        app: The application.
    """
    clients: list[TestClient] = []

    def login(pseudonym: str) -> TestClient:
        """Return a web client logged in as ``pseudonym``.

        Args:
            pseudonym: Whom to log in as.
        """
        client = TestClient(app, base_url=ORIGIN, headers={"Origin": ORIGIN})
        client.__enter__()
        clients.append(client)
        response = client.post("/api/auth/dev", json={"pseudonym": pseudonym})
        assert response.status_code == 204, response.text
        return client

    yield login
    for client in clients:
        client.__exit__(None, None, None)


@pytest.fixture
def plugin(app: FastAPI) -> Iterator[Callable[..., Plugin]]:
    """Make plugin installations confirmed by a human, each registering an Assistant.

    Args:
        app: The application.
    """
    clients: list[TestClient] = []

    def install(
        web: TestClient, project: str, team: str | None = None, session: str | None = "s1"
    ) -> Plugin:
        """Log a plugin in through the device code, confirmed by ``web``'s human.

        Args:
            web: The human's web client.
            project: Project name of the Assistant.
            team: The Team's slug its project is linked to, as a ``.coloqo.json`` names it.
            session: The Claude Code session the Assistant is.
        """
        client = TestClient(app, base_url=ORIGIN, headers={"X-Coloqo-Plugin": "0.5.0"})
        client.__enter__()
        clients.append(client)
        start = client.post("/api/device/start", json={"name": "laptop"}).json()
        assert web.post(f"/api/device/{start['user_code']}/approve").status_code == 200
        token = client.post("/api/device/token", json={"device_code": start["device_code"]})
        client.headers["Authorization"] = f"Bearer {token.json()['token']}"
        registered = client.post(
            "/api/assistant",
            json={
                "project_key": hashlib.sha256(project.encode()).hexdigest(),
                "project_name": project,
                "team": team,
                "session_id": session,
            },
        ).json()
        client.headers["X-Coloqo-Assistant"] = registered["key"]
        return Plugin(
            client=client,
            key=registered["key"],
            assistant=registered["name"],
            project_key=registered["project_key"],
            word=registered["word"],
        )

    yield install
    for client in clients:
        client.__exit__(None, None, None)


@pytest.fixture
def sibling(app: FastAPI) -> Iterator[Callable[..., Plugin]]:
    """Open another Claude Code session of the same project on the same computer (0024).

    Args:
        app: The application.
    """
    clients: list[TestClient] = []

    def open_session(first: Plugin, project: str, session: str) -> Plugin:
        """Register another session's Assistant with the first one's installation token.

        Args:
            first: An Assistant of the project, whose computer the new session runs on.
            project: The project's folder name.
            session: The new session's id.
        """
        client = TestClient(
            app,
            base_url=ORIGIN,
            headers={
                "Authorization": first.client.headers["Authorization"],
                "X-Coloqo-Plugin": "0.5.0",
            },
        )
        client.__enter__()
        clients.append(client)
        registered = client.post(
            "/api/assistant",
            json={
                "project_key": hashlib.sha256(project.encode()).hexdigest(),
                "project_name": project,
                "session_id": session,
            },
        ).json()
        client.headers["X-Coloqo-Assistant"] = registered["key"]
        return Plugin(
            client=client,
            key=registered["key"],
            assistant=registered["name"],
            project_key=registered["project_key"],
            word=registered["word"],
        )

    yield open_session
    for client in clients:
        client.__exit__(None, None, None)


@pytest.fixture
def live_url(app: FastAPI, settings: Settings) -> Iterator[str]:
    """Serve a second application on the same database with uvicorn, for streams.

    The test client cannot end an endless response; a real server sees the client leave.

    Args:
        app: The application, so the database is migrated and emptied first.
        settings: Instance settings.
    """
    server = uvicorn.Server(
        uvicorn.Config(create_app(settings), host="127.0.0.1", port=0, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started:
        assert time.monotonic() < deadline, "uvicorn did not start"
        time.sleep(0.05)
    port = server.servers[0].sockets[0].getsockname()[1]
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(10)


@dataclass
class Setup:
    """A Team of alice (owner) and bob, an Area, and an Assistant each.

    Attributes:
        alice: Alice's web client.
        bob: Bob's web client.
        alice_api: Alice's Assistant.
        bob_web: Bob's Assistant.
        team: The Team's slug, ``acme``.
        area: The Area's slug, ``contracts``.
    """

    alice: TestClient
    bob: TestClient
    alice_api: Plugin
    bob_web: Plugin
    team: str
    area: str


@pytest.fixture
def setup(human: Callable[[str], TestClient], plugin: Callable[..., Plugin]) -> Setup:
    """Build the Team.

    Args:
        human: Factory of logged-in web clients.
        plugin: Factory of plugin installations.
    """
    alice = human("alice")
    bob = human("bob")
    team = alice.post("/api/team", json={"name": "Acme"}).json()["slug"]
    url = alice.post(f"/api/team/{team}/invite").json()["url"]
    token = url.rsplit("/", 1)[1]
    assert bob.post(f"/api/invite/{token}/accept").json()["role"] == "member"
    area = alice.post(
        f"/api/team/{team}/area", json={"name": "Contracts", "description": "API contracts"}
    ).json()["slug"]
    return Setup(
        alice=alice,
        bob=bob,
        alice_api=plugin(alice, "billing-api", team),
        bob_web=plugin(bob, "web", team),
        team=team,
        area=area,
    )
