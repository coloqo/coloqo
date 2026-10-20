"""The Coloqo API as the plugin uses it (decision 0002)."""

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote

import httpx

from coloqo import __version__
from coloqo.config import load_token, server_url


class ColoqoError(Exception):
    """The server refused a request or could not be reached.

    Attributes:
        status: HTTP status, or 0 when the server was not reached.
        detail: The server's ``detail``: a message, or a dict with ``code`` and ``message``.
    """

    def __init__(self, status: int, detail: Any) -> None:
        """Keep the status and the server's explanation.

        Args:
            status: HTTP status, or 0.
            detail: The server's ``detail``.
        """
        self.status = status
        self.detail = detail
        message = detail.get("message", detail) if isinstance(detail, dict) else detail
        super().__init__(str(message))

    @property
    def code(self) -> str | None:
        """Return the machine-readable code of a structured refusal, if any."""
        return self.detail.get("code") if isinstance(self.detail, dict) else None


class NotLoggedIn(ColoqoError):
    """This computer has no valid installation token."""


LINK_FILE = ".coloqo.json"
"""The file a repository commits to link its projects to a Team (decision 0020)."""


def find_link_file(directory: Path) -> Path | None:
    """Return the ``.coloqo.json`` of a project: in it or a parent, up to the repository's root.

    Args:
        directory: The project directory.
    """
    for folder in (directory, *directory.parents):
        candidate = folder / LINK_FILE
        if candidate.is_file():
            return candidate
        if (folder / ".git").exists():
            return None
    return None


SLUG = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,38}[a-z0-9])?$")
"""A Team's slug (decision 0025)."""


def link_file_team(directory: Path) -> str | int | None:
    """Return the Team a project's ``.coloqo.json`` names; ``None`` without a usable file.

    A file names the Team by slug, ``{"team": "acme"}``. A file written before slugs names it
    by id, ``{"team_id": 3, "team": "Acme"}``, with the name for people; the id is returned
    then, and the server understands it for one more release.

    Args:
        directory: The project directory.
    """
    found = find_link_file(directory)
    if found is None:
        return None
    try:
        data = json.loads(found.read_text(encoding="utf-8"))
        old, team = data.get("team_id"), data.get("team")
    except (OSError, ValueError, AttributeError):
        return None
    if isinstance(old, int) and not isinstance(old, bool):
        return old
    return team if isinstance(team, str) and SLUG.match(team) else None


def session_id() -> str | None:
    """Return the Claude Code session the process serves, when Claude Code says so (0024)."""
    return os.environ.get("CLAUDE_CODE_SESSION_ID") or None


@dataclass
class Project:
    """The project an Assistant works in.

    Attributes:
        key: SHA-256 of the project's absolute path; the path itself is not sent.
        name: The project folder's name, part of the Assistant's name.
        team: The Team its ``.coloqo.json`` names, if the repository has one (decision 0020):
            a slug, or an id from a file written before slugs.
    """

    key: str
    name: str
    team: str | int | None = None

    @staticmethod
    def directory(directory: str | None = None) -> Path:
        """Return the project directory: given, Claude Code's project, or the current one.

        Args:
            directory: Project directory, if known.
        """
        return Path(
            directory
            or os.environ.get("COLOQO_PROJECT_DIR")
            or os.environ.get("CLAUDE_PROJECT_DIR")
            or os.getcwd()
        ).resolve()

    @classmethod
    def detect(cls, directory: str | None = None) -> "Project":
        """Find the project the Assistant works in.

        Args:
            directory: Project directory, if known.
        """
        path = cls.directory(directory)
        name = path.name or "project"
        return cls(
            key=hashlib.sha256(str(path).encode()).hexdigest(),
            name=name[:60],
            team=link_file_team(path),
        )


class Api:
    """A client of one Coloqo server, acting as one Assistant once registered."""

    def __init__(
        self, url: str | None = None, token: str | None = None, timeout: float = 30
    ) -> None:
        """Prepare a client; it connects on the first request.

        Args:
            url: Server address; ``COLOQO_URL`` or the cloud instance when omitted.
            token: Installation token; the saved one when omitted.
            timeout: Seconds to wait for the server.
        """
        self.url = url or server_url()
        self.token = token or load_token(self.url)
        headers = {"User-Agent": f"coloqo-plugin/{__version__}", "X-Coloqo-Plugin": __version__}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        self.http = httpx.Client(base_url=self.url, headers=headers, timeout=timeout)
        self.assistant_key: str | None = None
        self.assistant_name: str | None = None
        self.project_key: str | None = None
        self.team: str | None = None
        self.team_name: str | None = None

    def close(self) -> None:
        """Close the connection."""
        self.http.close()

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        """Call the API and return the decoded JSON.

        Args:
            method: HTTP method.
            path: Path under ``/api``.
            **kwargs: Passed to ``httpx``.

        Raises:
            NotLoggedIn: The token is missing, invalid or revoked.
            ColoqoError: The server refused the request or could not be reached.
        """
        if not self.token and not path.startswith("/device/"):
            raise NotLoggedIn(401, "This computer is not logged in to Coloqo")
        try:
            response = self.http.request(method, f"/api{path}", **kwargs)
        except httpx.HTTPError as error:
            raise ColoqoError(0, f"Coloqo at {self.url} is unreachable: {error}") from error
        if response.status_code == 401:
            raise NotLoggedIn(401, _detail(response))
        if response.status_code >= 400:
            raise ColoqoError(response.status_code, _detail(response))
        if response.status_code == 204 or not response.content:
            return None
        return response.json()

    def register(self, project: Project, session: str | None = None) -> str:
        """Register this session's Assistant for a project and act as it (decision 0024).

        Args:
            project: The project.
            session: The Claude Code session; the one the process serves when omitted.

        Raises:
            NotLoggedIn: The token is missing, invalid or revoked.
            ColoqoError: The server refused the request or could not be reached.
        """
        team = project.team
        registered = self.request(
            "POST",
            "/assistant",
            json={
                "project_key": project.key,
                "project_name": project.name,
                "team": team if isinstance(team, str) else None,
                "team_id": team if isinstance(team, int) else None,
                "session_id": session or session_id(),
            },
        )
        self.assistant_key = registered["key"]
        self.assistant_name = registered["name"]
        self.project_key = registered["project_key"]
        self.team = registered.get("team")
        self.team_name = registered.get("team_name")
        self.http.headers["X-Coloqo-Assistant"] = registered["key"]
        return registered["name"]

    def upload(self, team: str, number: int, path: Path) -> dict:
        """Upload a local file into a Topic.

        Args:
            team: The Team's slug.
            number: The Topic's number.
            path: The file.

        Raises:
            OSError: The file cannot be read.
            NotLoggedIn: The token is missing, invalid or revoked.
            ColoqoError: The server refused the file or could not be reached.
        """
        with path.open("rb") as content:
            return self.request(
                "POST",
                f"/team/{team}/topic/{number}/file",
                content=content,
                headers={
                    "X-File-Name": quote(path.name),
                    "Content-Type": "application/octet-stream",
                },
            )

    def download(self, team: str, number: int, folder: Path, target: Path | None = None) -> Path:
        """Download a file of a Team and return where it was written.

        Args:
            team: The Team's slug.
            number: The file's number in the Team.
            folder: Folder for the file under its own name, when ``target`` is not given.
            target: Exact path to write.

        Raises:
            OSError: The file cannot be written.
            NotLoggedIn: The token is missing, invalid or revoked.
            ColoqoError: The server refused or could not be reached.
        """
        if not self.token:
            raise NotLoggedIn(401, "This computer is not logged in to Coloqo")
        try:
            with self.http.stream("GET", f"/api/team/{team}/file/{number}") as response:
                if response.status_code >= 400:
                    response.read()
                    error = NotLoggedIn if response.status_code == 401 else ColoqoError
                    raise error(response.status_code, _detail(response))
                if target is None:
                    name = _file_name(response.headers.get("content-disposition", ""))
                    target = folder / (name or f"file-{number}")
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("wb") as out:
                    for chunk in response.iter_bytes():
                        out.write(chunk)
                return target
        except httpx.HTTPError as error:
            raise ColoqoError(0, f"Coloqo at {self.url} is unreachable: {error}") from error


def _file_name(disposition: str) -> str | None:
    """Return a safe file name from a ``Content-Disposition`` header.

    Args:
        disposition: The header.
    """
    match = re.search(r"filename\*=utf-8''([^;]+)", disposition, re.IGNORECASE) or re.search(
        r'filename="?([^";]+)"?', disposition
    )
    if not match:
        return None
    name = os.path.basename(unquote(match.group(1)).replace("\\", "/")).strip()
    return name if name not in ("", ".", "..") else None


def _detail(response: httpx.Response) -> Any:
    """Return the ``detail`` of an error response, or its text.

    Args:
        response: The error response.
    """
    try:
        return response.json().get("detail", response.text)
    except ValueError:
        return response.text or f"HTTP {response.status_code}"
