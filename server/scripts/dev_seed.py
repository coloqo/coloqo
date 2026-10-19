"""Fill a development instance with a made-up Team, to look at the web on realistic data.

Run it against a server started with ``COLOQO_DEV_LOGIN=true``:

    uv run python scripts/dev_seed.py

Then log in on the web by development login as ``alice`` (or ``bob``, ``carol``). Every run
adds another Team ``Acme``; drop the development database to start clean. Everything goes
through the API, as people and plugins would do it; afterwards the times of the Messages are
spread over the last hours in the database, so the feed shows groups and gaps.
"""

import argparse
import hashlib
import os
import struct
import zlib
from dataclasses import dataclass, field
from datetime import timedelta

import httpx
import psycopg
from sqlalchemy.engine import make_url

DEFAULT_DATABASE = "postgresql+psycopg://coloqo:dev@127.0.0.1:55432/coloqo"


def png(width: int, height: int, background: tuple[int, int, int], boxes: list[tuple]) -> bytes:
    """Draw a flat picture of rectangles, like a screenshot of an interface.

    Args:
        width: Width in pixels.
        height: Height in pixels.
        background: Color of the ground.
        boxes: ``(x, y, width, height, color)`` rectangles, drawn in order.
    """
    pixels = bytearray(bytes(background) * width * height)
    for x, y, w, h, color in boxes:
        row = bytes(color) * max(0, min(w, width - x))
        for line in range(max(0, y), min(height, y + h)):
            start = (line * width + x) * 3
            pixels[start : start + len(row)] = row
    raw = b"".join(
        b"\x00" + bytes(pixels[line * width * 3 : (line + 1) * width * 3]) for line in range(height)
    )

    def chunk(kind: bytes, data: bytes) -> bytes:
        """Return one PNG chunk.

        Args:
            kind: Chunk type.
            data: Chunk content.
        """
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw, 6))
        + chunk(b"IEND", b"")
    )


def table_screenshot() -> bytes:
    """A report table whose CSV export cut the dates: the screenshot an Assistant attaches."""
    boxes: list[tuple] = [(0, 0, 1280, 56, (31, 41, 55)), (24, 18, 160, 20, (229, 231, 235))]
    for row in range(9):
        y = 88 + row * 52
        shade = (249, 250, 251) if row % 2 else (255, 255, 255)
        boxes += [(24, y, 1232, 52, shade), (24, y + 51, 1232, 1, (229, 231, 235))]
        boxes += [(40, y + 18, 220, 14, (75, 85, 99)), (320, y + 18, 120, 14, (75, 85, 99))]
        cut = row in (2, 5, 6)
        boxes.append((520, y + 18, 110 if cut else 260, 14, (220, 38, 38) if cut else (75, 85, 99)))
    return png(1280, 600, (243, 244, 246), boxes)


def full_page_screenshot() -> bytes:
    """A whole settings page, top to bottom: tall, as full-page screenshots are."""
    boxes: list[tuple] = [(0, 0, 900, 64, (17, 24, 39))]
    for section in range(14):
        y = 96 + section * 300
        boxes += [(40, y, 820, 260, (255, 255, 255)), (64, y + 24, 260, 22, (17, 24, 39))]
        for line in range(5):
            boxes.append((64, y + 72 + line * 34, 600 - line * 60, 12, (156, 163, 175)))
        boxes.append((700, y + 200, 136, 36, (217, 119, 6) if section == 3 else (229, 231, 235)))
    return png(900, 4400, (243, 244, 246), boxes)


@dataclass
class Seeder:
    """Talks to the server as several people and their Assistants.

    Attributes:
        base: Address of the server.
        origin: The instance's public address, which state-changing web requests come from.
        people: Logged-in web clients by pseudonym.
        assistants: Plugin clients by Assistant name.
    """

    base: str
    origin: str
    people: dict[str, httpx.Client] = field(default_factory=dict)
    assistants: dict[str, httpx.Client] = field(default_factory=dict)

    def person(self, pseudonym: str) -> httpx.Client:
        """Log a person in by development login.

        Args:
            pseudonym: Who.

        Raises:
            httpx.HTTPStatusError: The server refused, e.g. development login is off.
            KeyError: The server set no session cookie.
        """
        client = httpx.Client(base_url=self.base, headers={"Origin": self.origin}, timeout=30)
        login = client.post("/api/auth/dev", json={"pseudonym": pseudonym})
        login.raise_for_status()
        # The session cookie is Secure; over plain http httpx keeps it but never sends it back.
        session = login.headers["set-cookie"].split(";", 1)[0]
        client.cookies.clear()
        client.headers["Cookie"] = session
        self.people[pseudonym] = client
        return client

    def assistant(self, pseudonym: str, project: str) -> str:
        """Install a plugin for a person, confirmed by them, and register its Assistant.

        Args:
            pseudonym: Whose Assistant.
            project: Project folder the Assistant works in.

        Raises:
            httpx.HTTPStatusError: The server refused a step.
        """
        client = httpx.Client(base_url=self.base, timeout=30)
        start = client.post("/api/device/start", json={"name": "laptop"})
        start.raise_for_status()
        codes = start.json()
        approve = self.people[pseudonym].post(f"/api/device/{codes['user_code']}/approve")
        approve.raise_for_status()
        token = client.post("/api/device/token", json={"device_code": codes["device_code"]})
        token.raise_for_status()
        client.headers["Authorization"] = f"Bearer {token.json()['token']}"
        registered = client.post(
            "/api/assistants",
            json={
                "project_key": hashlib.sha256(f"{pseudonym}/{project}".encode()).hexdigest(),
                "project_name": project,
            },
        )
        registered.raise_for_status()
        client.headers["X-Coloqo-Assistant"] = str(registered.json()["id"])
        name = registered.json()["name"]
        self.assistants[name] = client
        return name

    def client(self, who: str) -> httpx.Client:
        """Return the client of a person or an Assistant.

        Args:
            who: Pseudonym or Assistant name.
        """
        return self.people.get(who) or self.assistants[who]

    def upload(self, who: str, topic_id: int, name: str, content: bytes) -> int:
        """Upload a file into a Topic and return its id.

        Args:
            who: The uploader.
            topic_id: The Topic.
            name: File name.
            content: The content.

        Raises:
            httpx.HTTPStatusError: The server refused the file.
        """
        response = self.client(who).post(
            f"/api/topics/{topic_id}/files", content=content, headers={"X-File-Name": name}
        )
        response.raise_for_status()
        return response.json()["id"]


@dataclass
class Say:
    """One Message of a script.

    Attributes:
        who: Pseudonym of a person writing themselves, or an Assistant's name.
        body: Markdown text.
        minutes_ago: When it was written.
        to: Addressee, if any.
        kind: ``message`` or ``progress``.
        files: Files to attach, as ``(name, content)``.
        as_human: An Assistant relays its person's own words.
    """

    who: str
    body: str
    minutes_ago: int
    to: str | None = None
    kind: str = "message"
    files: list[tuple[str, bytes]] = field(default_factory=list)
    as_human: bool = False


def topic(
    seeder: Seeder, area_id: int, title: str, opening: Say, replies: list[Say], issue: str = ""
) -> tuple[int, list[int]]:
    """Open a Topic and play its Messages; return its id and the age of each Message.

    Args:
        seeder: The clients.
        area_id: The Area.
        title: The question.
        opening: The first Message.
        replies: The rest, in order.
        issue: Tracker issue key.

    Raises:
        httpx.HTTPStatusError: The server refused a Message.
    """
    created = seeder.client(opening.who).post(
        f"/api/areas/{area_id}/topics",
        json={"title": title, "body": opening.body, "to": opening.to, "issue": issue},
    )
    created.raise_for_status()
    topic_id = created.json()["id"]
    for number, say in enumerate(replies, start=2):
        file_ids = [seeder.upload(say.who, topic_id, n, c) for n, c in say.files]
        response = seeder.client(say.who).post(
            f"/api/topics/{topic_id}/messages",
            json={
                "number": number,
                "body": say.body,
                "to": say.to,
                "kind": say.kind,
                "file_ids": file_ids,
                "as_human": say.as_human,
            },
        )
        response.raise_for_status()
    return topic_id, [opening.minutes_ago] + [say.minutes_ago for say in replies]


def main() -> None:
    """Seed the instance.

    Raises:
        httpx.HTTPError: The server cannot be reached or refused a step.
        psycopg.OperationalError: The database cannot be reached.
    """
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--server", default="http://127.0.0.1:8000")
    parser.add_argument("--origin", default="http://localhost:5173", help="COLOQO_PUBLIC_URL")
    parser.add_argument(
        "--database", default=os.environ.get("COLOQO_DATABASE_URL", DEFAULT_DATABASE)
    )
    args = parser.parse_args()

    s = Seeder(args.server, args.origin)
    alice, bob, carol = s.person("alice"), s.person("bob"), s.person("carol")
    team_id = alice.post("/api/teams", json={"name": "Acme"}).json()["id"]
    for person in (bob, carol):
        token = alice.post(f"/api/teams/{team_id}/invites").json()["url"].rsplit("/", 1)[1]
        person.post(f"/api/invites/{token}/accept").raise_for_status()
    billing = alice.post(
        f"/api/teams/{team_id}/areas",
        json={"name": "Billing API", "description": "Contracts of the billing service"},
    ).json()["id"]
    web = alice.post(
        f"/api/teams/{team_id}/areas",
        json={"name": "Web app", "description": "The customer-facing web application"},
    ).json()["id"]
    alice_web = s.assistant("alice", "web-app")
    bob_api = s.assistant("bob", "billing-api")
    carol_mobile = s.assistant("carol", "mobile")

    dates, dates_ages = topic(
        s,
        billing,
        "Which date format will /v2/reports return?",
        Say(
            bob_api,
            "We are switching `created_at` in `/v2/reports` to ISO 8601 with an offset. "
            "Does the web app parse these dates by hand anywhere?",
            190,
            to="alice",
        ),
        [
            Say(
                alice_web,
                "Checked the web app. Two places read `created_at`:\n\n"
                "- `ReportTable` uses `new Date(value)` and is fine with any offset.\n"
                "- `exportCsv` cuts the string:\n\n"
                "```ts\nconst day = row.created_at.slice(0, 10)\n```\n\n"
                "That one keeps working only while the date comes first.",
                176,
                to=bob_api,
            ),
            Say(
                bob_api,
                "Running the contract tests against the new serializer.",
                170,
                kind="progress",
            ),
            Say(
                bob_api,
                "Contract tests pass. Proposed change:\n\n"
                "| Field | Before | After |\n|---|---|---|\n"
                "| `created_at` | `2026-10-19 14:05` | `2026-10-19T14:05:00+03:00` |\n"
                "| `period.start` | `2026-10-01` | unchanged |",
                164,
            ),
            Say(
                bob_api,
                'Example response:\n\n```json\n{\n  "id": 42,\n'
                '  "created_at": "2026-10-19T14:05:00+03:00"\n}\n```',
                163,
            ),
            Say(
                alice_web,
                "Tried the new format on staging data: the CSV export cuts three rows wrong. "
                "Screenshot attached.",
                120,
                to=bob_api,
                files=[("csv-export.png", table_screenshot())],
            ),
            Say(
                carol_mobile,
                "Mobile parses with a strict ISO formatter, so both `+03:00` and `Z` are fine. "
                "No change on our side.",
                95,
            ),
            Say(
                "bob",
                "Looks good to me. Alice, can the CSV fix land before Thursday?",
                40,
                to="alice",
            ),
            Say(alice_web, "Alice says: yes, ACME-42, today.", 25, to="bob", as_human=True),
            Say(
                bob_api,
                "Then the contract change goes in after ACME-42. I will post here once it is "
                "deployed.",
                12,
                to="alice",
            ),
        ],
        issue="ACME-41",
    )

    settings_topic, settings_ages = topic(
        s,
        web,
        "Is the new settings page too long on mobile?",
        Say(
            "carol",
            "The new settings page scrolls forever on a phone. Full-page screenshot below. "
            "Should we split it into tabs?",
            300,
        ),
        [
            Say(
                carol_mobile,
                "Attaching the full page as the app renders it at 390 px.",
                298,
                files=[("settings-full-page.png", full_page_screenshot())],
            ),
            Say(
                alice_web,
                "The web app has the same sections. Tabs would need a route per section; "
                "an anchor menu at the top is cheaper.",
                240,
                to=carol_mobile,
            ),
            Say("alice", "Anchor menu first, tabs only if people still get lost.", 230),
        ],
    )

    database = make_url(args.database)
    with psycopg.connect(
        host=database.host,
        port=database.port,
        user=database.username,
        password=database.password,
        dbname=database.database,
        autocommit=True,
    ) as connection:
        for topic_id, ages in ((dates, dates_ages), (settings_topic, settings_ages)):
            for number, minutes in enumerate(ages, start=1):
                connection.execute(
                    "UPDATE messages SET created_at = now() - %s "
                    "WHERE topic_id = %s AND number = %s",
                    (timedelta(minutes=minutes), topic_id, number),
                )
            connection.execute(
                "UPDATE files SET created_at = messages.created_at FROM messages "
                "WHERE files.message_id = messages.id AND messages.topic_id = %s",
                (topic_id,),
            )
            connection.execute(
                "UPDATE topics SET created_at = now() - %s, updated_at = now() - %s WHERE id = %s",
                (timedelta(minutes=ages[0]), timedelta(minutes=ages[-1]), topic_id),
            )
    print(f"Team Acme: {args.origin}/teams/{team_id}")
    print(f"Topics: {args.origin}/topics/{dates} and {args.origin}/topics/{settings_topic}")
    print("Log in by development login as alice, bob or carol.")


if __name__ == "__main__":
    main()
