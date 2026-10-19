"""Tests of people's avatars: re-encoded, from GitHub once, served to their Teams (0019)."""

import io
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from coloqo_server.api import avatars
from coloqo_server.settings import Settings
from tests.conftest import Setup, _connect


def _photo(width: int, height: int, gps: bool = False) -> bytes:
    """Make a JPEG photo, with a GPS position in its metadata if asked.

    Args:
        width: Width in pixels.
        height: Height in pixels.
        gps: Put a GPS block into the EXIF.
    """
    picture = Image.new("RGB", (width, height), (200, 80, 40))
    exif = Image.Exif()
    if gps:
        exif[0x8825] = {1: "N", 2: (55.0, 45.0, 0.0)}
    out = io.BytesIO()
    picture.save(out, "JPEG", exif=exif)
    return out.getvalue()


def test_upload_is_squared_and_stripped(setup: Setup) -> None:
    """An uploaded photo becomes a 256-pixel square WebP without its metadata.

    Args:
        setup: The Team.
    """
    uploaded = setup.alice.put("/api/me/avatar", content=_photo(1200, 800, gps=True))
    me = setup.alice.get("/api/me").json()
    served = setup.bob.get(me["avatar"])

    stored = Image.open(io.BytesIO(served.content))
    assert uploaded.status_code == 204
    assert me["avatar"].endswith("?v=1")
    assert (stored.format, stored.size) == ("WEBP", (256, 256))
    assert not stored.getexif()
    assert served.headers["content-type"] == "image/webp"
    assert "sandbox" in served.headers["content-security-policy"]


def test_members_see_avatars_and_strangers_do_not(
    setup: Setup, human: Callable[[str], TestClient]
) -> None:
    """A Team lists its people's avatars; someone sharing no Team gets 404.

    Args:
        setup: The Team.
        human: Factory of logged-in web clients.
    """
    setup.bob.put("/api/me/avatar", content=_photo(300, 300))
    team = setup.alice.get(f"/api/teams/{setup.team_id}").json()
    bob = next(m for m in team["members"] if m["pseudonym"] == "bob")

    assert bob["avatar"] is not None
    assert human("eve").get(bob["avatar"]).status_code == 404


def test_not_a_picture_is_refused_and_removal_restores_initials(setup: Setup) -> None:
    """Text is refused as an avatar; removing one brings the initials back.

    Args:
        setup: The Team.
    """
    refused = setup.alice.put("/api/me/avatar", content=b"<svg/>")
    setup.alice.put("/api/me/avatar", content=_photo(64, 64))
    removed = setup.alice.delete("/api/me/avatar")

    assert refused.status_code == 422
    assert removed.status_code == 204
    assert setup.alice.get("/api/me").json()["avatar"] is None


def test_plugin_cannot_set_an_avatar(setup: Setup) -> None:
    """Only the person, in the web, sets their avatar.

    Args:
        setup: The Team.
    """
    assert setup.alice_api.client.put("/api/me/avatar", content=_photo(64, 64)).status_code == 403


def test_github_avatar_is_taken_once_by_the_server(
    setup: Setup, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The server takes the GitHub avatar by the GitHub id; without a GitHub login it cannot.

    Args:
        setup: The Team.
        settings: Instance settings.
        monkeypatch: Patching helper from pytest.
    """
    asked: list[str] = []

    async def fetch(url: str) -> bytes:
        """Stand in for GitHub.

        Args:
            url: The avatar's address.
        """
        asked.append(url)
        return _photo(460, 460)

    monkeypatch.setattr(avatars, "fetch_github_avatar", fetch)
    without = setup.bob.post("/api/me/avatar/github")
    me = setup.alice.get("/api/me").json()
    with _connect(settings.database_url) as connection:
        connection.execute(
            "INSERT INTO identities (user_id, provider, subject) VALUES (%s, 'github', '583231')",
            (me["id"],),
        )

    taken = setup.alice.post("/api/me/avatar/github")

    assert without.status_code == 409
    assert taken.status_code == 204
    assert asked == ["https://avatars.githubusercontent.com/u/583231?s=256"]
    assert setup.alice.get("/api/me").json() | {"avatar": None} == me | {"github": True}
