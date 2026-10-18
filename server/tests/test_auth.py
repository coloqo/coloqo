"""Tests of logging in: providers, pseudonyms, the plugin's device code, origins."""

from collections.abc import Callable
from urllib.parse import parse_qs, urlsplit

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.conftest import ORIGIN, Plugin


def test_github_login_creates_user_without_pseudonym(app: FastAPI) -> None:
    """A first provider login creates a User who then chooses a name.

    Args:
        app: The application.
    """
    with TestClient(app, base_url=ORIGIN, headers={"Origin": ORIGIN}) as client:
        start = client.get("/api/auth/github/start?next=/teams", follow_redirects=False)
        state = parse_qs(urlsplit(start.headers["location"]).query)["state"][0]

        callback = client.get(f"/api/auth/github/callback?code=id-42&state={state}")

        assert callback.status_code == 200
        assert 'content="0;url=/teams"' in callback.text
        assert client.get("/api/me").json()["pseudonym"] is None
        assert client.get("/api/teams").status_code == 403
        assert client.put("/api/me/pseudonym", json={"pseudonym": "alice"}).status_code == 200
        assert client.get("/api/me").json()["pseudonym"] == "alice"


def test_github_login_twice_finds_the_same_user(app: FastAPI) -> None:
    """The provider id finds the existing User.

    Args:
        app: The application.
    """
    ids = []
    for _ in range(2):
        with TestClient(app, base_url=ORIGIN) as client:
            start = client.get("/api/auth/github/start", follow_redirects=False)
            state = parse_qs(urlsplit(start.headers["location"]).query)["state"][0]
            client.get(f"/api/auth/github/callback?code=id-7&state={state}")
            ids.append(client.get("/api/me").json()["id"])

    assert ids[0] == ids[1]


def test_callback_with_wrong_state_is_refused(app: FastAPI) -> None:
    """A callback that does not bring back the state is refused.

    Args:
        app: The application.
    """
    with TestClient(app, base_url=ORIGIN) as client:
        client.get("/api/auth/github/start", follow_redirects=False)

        response = client.get("/api/auth/github/callback?code=id-1&state=forged")

        assert response.status_code == 400


def test_pseudonym_is_unique_and_checked(human: Callable[[str], TestClient]) -> None:
    """A taken or malformed name is refused.

    Args:
        human: Factory of logged-in web clients.
    """
    human("alice")
    bob = human("bob")

    assert bob.put("/api/me/pseudonym", json={"pseudonym": "ALICE"}).status_code == 409
    assert bob.put("/api/me/pseudonym", json={"pseudonym": "b o b"}).status_code == 422


def test_cookie_request_from_another_origin_is_refused(
    human: Callable[[str], TestClient],
) -> None:
    """A state-changing request with the session cookie needs this instance's origin.

    Args:
        human: Factory of logged-in web clients.
    """
    alice = human("alice")

    forged = alice.post("/api/teams", json={"name": "Acme"}, headers={"Origin": "https://evil"})

    assert forged.status_code == 403
    assert alice.post("/api/teams", json={"name": "Acme"}).status_code == 201


def test_device_login_gives_a_token_once(
    human: Callable[[str], TestClient], plugin: Callable[[TestClient, str], Plugin]
) -> None:
    """The confirmed code yields a token that acts for the human and its Assistant.

    Args:
        human: Factory of logged-in web clients.
        plugin: Factory of plugin installations.
    """
    alice = human("alice")
    installed = plugin(alice, "billing-api")

    me = installed.client.get("/api/me").json()

    assert me == {
        "id": me["id"],
        "pseudonym": "alice",
        "via": "plugin",
        "assistant": "alice · billing-api",
        "providers": ["github"],
    }


def test_pending_and_denied_device_login(app: FastAPI, human: Callable[[str], TestClient]) -> None:
    """Polling reports a pending code, then a denied one.

    Args:
        app: The application.
        human: Factory of logged-in web clients.
    """
    alice = human("alice")
    with TestClient(app, base_url=ORIGIN) as client:
        start = client.post("/api/device/start", json={"name": "laptop"}).json()
        poll = {"device_code": start["device_code"]}

        assert (
            client.post("/api/device/token", json=poll).json()["detail"] == "authorization_pending"
        )
        code = start["user_code"].lower().replace("-", "")
        assert alice.get(f"/api/device/{code}").json()["state"] == "pending"
        alice.post(f"/api/device/{code}/deny")
        assert client.post("/api/device/token", json=poll).json()["detail"] == "access_denied"


def test_revoked_installation_is_refused(
    human: Callable[[str], TestClient], plugin: Callable[[TestClient, str], Plugin]
) -> None:
    """Revoking an installation in the web stops its token.

    Args:
        human: Factory of logged-in web clients.
        plugin: Factory of plugin installations.
    """
    alice = human("alice")
    installed = plugin(alice, "api")
    (installation,) = alice.get("/api/installations").json()

    assert alice.delete(f"/api/installations/{installation['id']}").status_code == 204
    assert installed.client.get("/api/me").status_code == 401


def test_plugin_cannot_take_human_actions(
    human: Callable[[str], TestClient], plugin: Callable[[TestClient, str], Plugin]
) -> None:
    """Human-only actions refuse the installation token (decision 0003).

    Args:
        human: Factory of logged-in web clients.
        plugin: Factory of plugin installations.
    """
    alice = human("alice")
    installed = plugin(alice, "api")

    assert installed.client.post("/api/teams", json={"name": "Acme"}).status_code == 403
    assert installed.client.get("/api/installations").status_code == 403


def test_foreign_assistant_id_is_refused(
    human: Callable[[str], TestClient], plugin: Callable[[TestClient, str], Plugin]
) -> None:
    """An installation cannot act as another installation's Assistant.

    Args:
        human: Factory of logged-in web clients.
        plugin: Factory of plugin installations.
    """
    alice_plugin = plugin(human("alice"), "api")
    bob_plugin = plugin(human("bob"), "web")

    response = bob_plugin.client.get(
        "/api/me", headers={"X-Coloqo-Assistant": str(alice_plugin.assistant_id)}
    )

    assert response.status_code == 403
