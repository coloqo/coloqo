"""Login providers behind one interface (decision 0009, joint 3)."""

from typing import Protocol
from urllib.parse import urlencode

import httpx


class ProviderError(Exception):
    """The provider refused the login or could not be reached."""


class LoginProvider(Protocol):
    """An external provider that tells who the person is (decision 0003)."""

    name: str

    def authorize_url(self, state: str, redirect_uri: str) -> str:
        """Return the provider's page the browser is sent to.

        Args:
            state: Random value the callback must bring back.
            redirect_uri: Where the provider returns the browser.
        """
        ...

    async def subject(self, code: str, redirect_uri: str) -> str:
        """Exchange the callback's code for the person's id at the provider.

        Args:
            code: The code from the callback.
            redirect_uri: The same address as in ``authorize_url``.

        Raises:
            ProviderError: The code is not accepted or the provider is unreachable.
        """
        ...


class GitHub:
    """GitHub OAuth App login without scopes: only the public id is read (decision 0014)."""

    name = "github"

    def __init__(self, client_id: str, client_secret: str) -> None:
        """Use the given OAuth App.

        Args:
            client_id: Client ID of the OAuth App.
            client_secret: Client secret of the OAuth App.
        """
        self.client_id = client_id
        self.client_secret = client_secret

    def authorize_url(self, state: str, redirect_uri: str) -> str:
        """Return GitHub's authorization page.

        Args:
            state: Random value the callback must bring back.
            redirect_uri: Where GitHub returns the browser.
        """
        query = urlencode(
            {
                "client_id": self.client_id,
                "redirect_uri": redirect_uri,
                "state": state,
                "allow_signup": "true",
            }
        )
        return f"https://github.com/login/oauth/authorize?{query}"

    async def subject(self, code: str, redirect_uri: str) -> str:
        """Return the GitHub user id for the callback's code.

        The access token is used once and not stored.

        Args:
            code: The code from the callback.
            redirect_uri: The same address as in ``authorize_url``.

        Raises:
            ProviderError: GitHub refuses the code or cannot be reached.
        """
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                token_response = await client.post(
                    "https://github.com/login/oauth/access_token",
                    headers={"Accept": "application/json"},
                    data={
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "code": code,
                        "redirect_uri": redirect_uri,
                    },
                )
                access_token = token_response.json().get("access_token")
                if not access_token:
                    raise ProviderError(f"GitHub refused the code: {token_response.text[:200]}")
                user_response = await client.get(
                    "https://api.github.com/user",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Accept": "application/vnd.github+json",
                    },
                )
                user_response.raise_for_status()
                return str(user_response.json()["id"])
        except (httpx.HTTPError, ValueError, KeyError) as error:
            raise ProviderError(f"GitHub login failed: {error}") from error
