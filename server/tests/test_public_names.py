"""Tests of slugs, per-Team numbers, the feed's window and the human's part (0025, 0026)."""

from collections.abc import Callable

from fastapi.testclient import TestClient

from tests.conftest import Plugin, Setup
from tests.test_topics import _open, _upload


def test_team_slug_is_offered_from_the_name(human: Callable[[str], TestClient]) -> None:
    """A slug comes from the name, transliterated, and gets a number when taken.

    Args:
        human: Factory of logged-in web clients.
    """
    alice = human("alice")

    first = alice.post("/api/team", json={"name": "Платёжный сервис"}).json()
    second = alice.post("/api/team", json={"name": "Платёжный  Сервис!"}).json()
    chosen = alice.post("/api/team", json={"name": "Acme", "slug": "acme-corp"}).json()
    taken = alice.post("/api/team", json={"name": "X", "slug": "acme-corp"})
    bad = alice.post("/api/team", json={"name": "X", "slug": "Acme Corp"})

    assert (first["slug"], second["slug"], chosen["slug"]) == (
        "platyozhnyy-servis",
        "platyozhnyy-servis-2",
        "acme-corp",
    )
    assert (taken.status_code, bad.status_code) == (409, 422)


def test_renamed_team_keeps_its_former_address(
    setup: Setup, human: Callable[[str], TestClient]
) -> None:
    """A former slug keeps leading to the Team and stays taken; going back frees it again.

    Args:
        setup: The Team.
        human: Factory of logged-in web clients.
    """
    number = _open(setup)["number"]
    renamed = setup.alice.patch(f"/api/team/{setup.team}", json={"slug": "acme-inc"}).json()
    carol = human("carol")

    old_team = setup.bob.get("/api/team/acme").json()
    old_topic = setup.bob.get(f"/api/team/acme/topic/{number}").json()
    squatted = carol.post("/api/team", json={"name": "Acme", "slug": "acme"})
    offered = carol.post("/api/team", json={"name": "Acme"}).json()
    back = setup.alice.patch("/api/team/acme-inc", json={"slug": "acme"}).json()
    by_member = setup.bob.patch("/api/team/acme", json={"slug": "bobs"})

    assert renamed["slug"] == "acme-inc"
    assert (old_team["slug"], old_topic["team"]) == ("acme-inc", "acme-inc")
    assert squatted.status_code == 409
    assert offered["slug"] == "acme-2"
    assert back["slug"] == "acme"
    assert setup.bob.get("/api/team/acme-inc").json()["slug"] == "acme"
    assert by_member.status_code == 403


def test_area_slug_and_its_former_one(setup: Setup) -> None:
    """An Area has a slug in its Team; renamed, the former one still finds its Topics.

    Args:
        setup: The Team.
    """
    _open(setup)
    other = setup.alice.post(f"/api/team/{setup.team}/area", json={"name": "Contracts"})
    renamed = setup.alice.patch(
        f"/api/team/{setup.team}/area/contracts", json={"slug": "api", "name": "API"}
    ).json()
    clash = setup.alice.post(
        f"/api/team/{setup.team}/area", json={"name": "Other", "slug": "contracts"}
    )

    by_former = setup.bob.get(f"/api/team/{setup.team}/topic", params={"area": "contracts"})
    by_current = setup.bob.get(f"/api/team/{setup.team}/topic", params={"area": "api"})

    assert other.status_code == 409
    assert (renamed["slug"], renamed["name"], renamed["open_topics"]) == ("api", "API", 1)
    assert clash.status_code == 409
    assert [t["area"] for t in by_former.json()] == ["api"]
    assert by_current.json() == by_former.json()


def test_files_are_numbered_per_team(setup: Setup, human: Callable[[str], TestClient]) -> None:
    """Files take numbers in their Team; another Team starts at 1 again (decision 0025).

    Args:
        setup: The Team.
        human: Factory of logged-in web clients.
    """
    first, second = _open(setup)["number"], _open(setup)["number"]
    a = _upload(setup.alice, first, "a.txt", b"a", "text/plain")
    b = _upload(setup.alice, second, "b.txt", b"b", "text/plain")
    globex = setup.alice.post("/api/team", json={"name": "Globex"}).json()["slug"]
    setup.alice.post(f"/api/team/{globex}/area", json={"name": "Dev"})
    topic = setup.alice.post(
        f"/api/team/{globex}/topic", json={"area": "dev", "title": "Q", "body": "x"}
    ).json()["number"]
    c = setup.alice.post(
        f"/api/team/{globex}/topic/{topic}/file", content=b"c", headers={"X-File-Name": "c.txt"}
    ).json()

    attached = setup.bob.post(
        f"/api/team/{setup.team}/topic/{second}/message",
        json={"number": 2, "body": "see", "files": [b["number"]]},
    )
    foreign = setup.bob.post(
        f"/api/team/{setup.team}/topic/{second}/message",
        json={"number": 3, "body": "see", "files": [a["number"]]},
    )

    assert (a["number"], b["number"], c["number"]) == (1, 2, 1)
    assert setup.bob.get(f"/api/team/{setup.team}/file/2").content == b"b"
    assert setup.alice.get(f"/api/team/{globex}/file/1").content == b"c"
    assert human("eve").get(f"/api/team/{setup.team}/file/1").status_code == 404
    assert attached.json()["files"][0]["number"] == 2
    assert foreign.status_code == 422


def _messages(setup: Setup, number: int, count: int) -> None:
    """Write numbered Messages 2 to ``count`` + 1 into a Topic, by Bob in the web.

    Args:
        setup: The Team.
        number: The Topic's number.
        count: How many.
    """
    for n in range(2, count + 2):
        response = setup.bob.post(
            f"/api/team/{setup.team}/topic/{number}/message", json={"number": n, "body": str(n)}
        )
        assert response.status_code == 201, response.text


def test_feed_window(setup: Setup) -> None:
    """The reader gets the last Messages, earlier ones before a number, later ones after.

    Args:
        setup: The Team.
    """
    number = _open(setup)["number"]
    _messages(setup, number, 9)
    path = f"/api/team/{setup.team}/topic/{number}"

    def numbers(**params: object) -> list[int]:
        """Return the numbers of the Messages a request brings.

        Args:
            **params: The query.
        """
        return [m["number"] for m in setup.alice.get(path, params=params).json()["messages"]]

    assert numbers(limit=3) == [8, 9, 10]
    assert numbers(limit=3, before=8) == [5, 6, 7]
    assert numbers(limit=3, before=3) == [1, 2]
    assert numbers(limit=3, after=0) == [1, 2, 3]


def test_feed_starts_at_the_first_unread_when_more_are_unread(setup: Setup) -> None:
    """With more unread than the window, the reader starts at the first unread Message.

    Args:
        setup: The Team.
    """
    number = _open(setup, to="bob")["number"]
    _messages(setup, number, 3)
    path = f"/api/team/{setup.team}/topic/{number}"
    setup.alice.post(f"{path}/read", json={"number": 2})
    for n in range(5, 10):
        setup.bob.post(f"{path}/message", json={"number": n, "body": str(n)})

    unread_first = setup.alice.get(path, params={"limit": 3, "from_unread": True}).json()
    few_unread = setup.bob.get(path, params={"limit": 3, "from_unread": True}).json()

    assert [m["number"] for m in unread_first["messages"]] == [3, 4, 5, 6, 7, 8, 9]
    assert [m["number"] for m in few_unread["messages"]] == [7, 8, 9]


def test_every_reply_of_an_assistant_names_the_human_part(
    setup: Setup, plugin: Callable[..., Plugin]
) -> None:
    """An Assistant's reply is "without", "with" or "words"; others carry no mark (0026).

    Args:
        setup: The Team.
        plugin: Factory of plugin installations.
    """
    number = _open(setup)["number"]
    path = f"/api/team/{setup.team}/topic/{number}"
    bob = setup.bob_web.client
    bob.post(f"{path}/message", json={"number": 2, "body": "own"})
    bob.post(f"{path}/message", json={"number": 3, "body": "asked", "with_human": True})
    bob.post(f"{path}/message", json={"number": 4, "body": "said", "as_human": True})
    bob.post(f"{path}/message", json={"number": 5, "body": "note", "kind": "progress"})
    setup.bob.post(f"{path}/message", json={"number": 6, "body": "typed"})
    setup.alice_api.client.post(f"{path}/stage", json={"text": "code"})

    messages = setup.alice.get(path).json()["messages"]

    assert [m["human_part"] for m in messages] == [
        "without",
        "without",
        "with",
        "words",
        None,
        None,
        None,
    ]
