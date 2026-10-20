"""Who is asking: web sessions, installation tokens, Assistants (decision 0003)."""

import hashlib
import secrets
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from coloqo_server.models import Assistant, Installation, Project, Team, User, WebSession

SESSION_COOKIE = "__Host-coloqo_session"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

SESSIONS_SINCE = (0, 5, 0)
"""The first plugin version that knows sessions and public names (decisions 0024, 0025); older
plugins are served the former paths and shapes for one more release."""


def new_token() -> str:
    """Return a fresh random token for a cookie, an installation or a link."""
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    """Return the SHA-256 the database keeps instead of the token itself.

    Args:
        token: The token as the client holds it.
    """
    return hashlib.sha256(token.encode()).hexdigest()


def now() -> datetime:
    """Return the current time, timezone-aware."""
    return datetime.now(UTC)


@dataclass
class Actor:
    """Who makes a request.

    Attributes:
        user: The User on whose behalf the request is made.
        installation: The plugin installation, or ``None`` for the web session.
        assistant: The Assistant, when the plugin names one in ``X-Coloqo-Assistant``.
        project: The Assistant's project, which holds the Team link (decision 0024).
        plugin: The plugin's version from ``X-Coloqo-Plugin``, as numbers; ``None`` for the web.
        legacy: A plugin older than 0.5.0: it gets the former paths' shapes (decision 0025).
    """

    user: User
    installation: Installation | None = None
    assistant: Assistant | None = None
    project: Project | None = None
    plugin: tuple[int, ...] | None = None
    legacy: bool = False

    @property
    def is_human(self) -> bool:
        """The request comes from the human's own web session."""
        return self.installation is None

    @property
    def team_id(self) -> int | None:
        """The Team the Assistant's project is linked to; ``None`` while unlinked or for the web."""
        return self.project.team_id if self.project else None


def plugin_version(text: str | None) -> tuple[int, ...] | None:
    """Read a version such as ``0.4.0``; ``None`` when there is none or it is not one.

    Args:
        text: The ``X-Coloqo-Plugin`` header.
    """
    if not text:
        return None
    parts = text.strip().split(".")
    if not all(part.isdigit() for part in parts):
        return None
    return tuple(int(part) for part in parts)


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    """Yield a database session for one request.

    Args:
        request: The incoming request; the application keeps the database in its state.
    """
    async with request.app.state.database.sessions() as session:
        yield session


DB = Annotated[AsyncSession, Depends(get_db)]


def _check_origin(request: Request) -> None:
    """Refuse a state-changing cookie request from another site (decision 0013).

    Args:
        request: The incoming request.

    Raises:
        HTTPException: 403 when ``Origin`` is missing or is not the instance's address.
    """
    if request.method in SAFE_METHODS:
        return
    expected = urlsplit(request.app.state.settings.public_url)
    origin = urlsplit(request.headers.get("origin", ""))
    if (origin.scheme, origin.netloc) != (expected.scheme, expected.netloc):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Request from another origin")


async def _web_user(request: Request, db: AsyncSession) -> User | None:
    """Return the User of the request's session cookie, if it is valid.

    Args:
        request: The incoming request.
        db: Database session.
    """
    cookie = request.cookies.get(SESSION_COOKIE)
    if not cookie:
        return None
    session = await db.scalar(
        select(WebSession).where(
            WebSession.token_hash == token_hash(cookie), WebSession.expires_at > now()
        )
    )
    return await db.get(User, session.user_id) if session else None


async def get_actor(
    request: Request,
    db: DB,
    authorization: Annotated[str | None, Header()] = None,
    x_coloqo_assistant: Annotated[str | None, Header()] = None,
    x_coloqo_plugin: Annotated[str | None, Header()] = None,
) -> Actor:
    """Identify the caller by an installation token or by the web session.

    Args:
        request: The incoming request.
        db: Database session.
        authorization: ``Bearer <installation token>`` from the plugin.
        x_coloqo_assistant: Key of the calling Assistant, registered by this installation; a
            plugin older than 0.5.0 sends its numeric id.
        x_coloqo_plugin: The plugin's version.

    Raises:
        HTTPException: 401 without valid credentials; 403 for a foreign Assistant id or a
            cookie request from another origin.
    """
    if authorization:
        scheme, _, token = authorization.partition(" ")
        installation = await db.scalar(
            select(Installation).where(
                Installation.token_hash == token_hash(token.strip()),
                Installation.revoked_at.is_(None),
            )
        )
        if scheme.lower() != "bearer" or installation is None:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                "The installation token is not valid or was revoked; run `coloqo login`",
            )
        installation.last_seen_at = now()
        version = plugin_version(x_coloqo_plugin)
        legacy = version is None or version < SESSIONS_SINCE
        assistant = None
        project = None
        if x_coloqo_assistant:
            named = x_coloqo_assistant.strip()
            if named.isdigit():
                assistant = await db.get(Assistant, int(named))
                legacy = True
            else:
                assistant = await db.scalar(select(Assistant).where(Assistant.key == named))
            if assistant is None or assistant.installation_id != installation.id:
                raise HTTPException(status.HTTP_403_FORBIDDEN, "Unknown Assistant")
            assistant.last_seen_at = installation.last_seen_at
            project = await db.get(Project, assistant.project_id)
        await db.commit()
        user = await db.get(User, installation.user_id)
        assert user is not None
        return Actor(
            user=user,
            installation=installation,
            assistant=assistant,
            project=project,
            plugin=version,
            legacy=legacy,
        )
    user = await _web_user(request, db)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not logged in")
    _check_origin(request)
    return Actor(user=user)


async def get_member_actor(actor: Annotated[Actor, Depends(get_actor)]) -> Actor:
    """Like ``get_actor``, and the User has chosen a pseudonym.

    Args:
        actor: The caller.

    Raises:
        HTTPException: 403 until the pseudonym is chosen in the web interface.
    """
    if actor.user.pseudonym is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Choose your name in the Coloqo web interface first"
        )
    return actor


async def get_human(actor: Annotated[Actor, Depends(get_actor)]) -> Actor:
    """Like ``get_actor``, for actions only a human may take, from the web (decision 0003).

    Args:
        actor: The caller.

    Raises:
        HTTPException: 403 for the plugin's installation token.
    """
    if not actor.is_human:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Only a human can do this, in the Coloqo web interface"
        )
    return actor


async def get_human_member(actor: Annotated[Actor, Depends(get_human)]) -> Actor:
    """A human from the web who has chosen a pseudonym.

    Args:
        actor: The caller.

    Raises:
        HTTPException: 403 until the pseudonym is chosen.
    """
    return await get_member_actor(actor)


ActorDep = Annotated[Actor, Depends(get_member_actor)]
AnyActorDep = Annotated[Actor, Depends(get_actor)]
HumanDep = Annotated[Actor, Depends(get_human_member)]
AnyHumanDep = Annotated[Actor, Depends(get_human)]


LINK_HINT = (
    "Link it: run `uvx coloqo link` and confirm in the browser, or commit a `.coloqo.json` "
    "naming the Team (decision 0020)."
)


def require_reader(actor: Actor) -> None:
    """Refuse Team data to an installation token that names no Assistant.

    Reading crosses the person's Teams, for the person or any of their Assistants (decision
    0020); a bare installation token is only for registering Assistants.

    Args:
        actor: The caller.

    Raises:
        HTTPException: 403 for a plugin request without an Assistant.
    """
    if actor.installation is not None and actor.assistant is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Name the Assistant in X-Coloqo-Assistant to read Teams"
        )


async def require_writer(db: AsyncSession, actor: Actor, team_id: int) -> None:
    """Refuse writing into a Team other than the one the caller's project is linked to.

    A human in the web writes in any of their Teams; an Assistant only in its linked Team.

    Args:
        db: Database session.
        actor: The caller, already known to be a member of the Team.
        team_id: The Team written to.

    Raises:
        HTTPException: 403 ``not_linked`` for an unlinked Assistant, ``other_team`` for one
            linked to another Team, or for a plugin request without an Assistant.
    """
    require_reader(actor)
    if actor.assistant is None or actor.team_id == team_id:
        return
    if actor.team_id is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            {
                "code": "not_linked",
                "message": "This project is not linked to a Team: its Assistant may read, "
                f"not write. {LINK_HINT}",
            },
        )
    linked = await db.get(Team, actor.team_id)
    target = await db.get(Team, team_id)
    raise HTTPException(
        status.HTTP_403_FORBIDDEN,
        {
            "code": "other_team",
            "message": f"This project is linked to «{linked.name if linked else '?'}»; it "
            f"writes only there. Write in «{target.name if target else '?'}» from the web, "
            "or relink the project in the web settings.",
        },
    )


def pushed_teams(actor: Actor) -> set[int] | None:
    """Return the Teams whose news may reach the caller unasked: the Inbox, the event stream.

    Args:
        actor: The caller.

    Returns:
        ``None`` for the web, where every Team of the person counts; the linked Team for an
        Assistant; an empty set for an unlinked one, which is told nothing (decision 0020).
    """
    if actor.assistant is None:
        return None
    return {actor.team_id} if actor.team_id else set()
