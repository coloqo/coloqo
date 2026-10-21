"""Assistants as sessions, their projects and the link to a Team (decisions 0020, 0024, 0025)."""

import hashlib
import re
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from coloqo_server.api.teams import LIVE, SHOWN, AssistantOut, assistant_out, find_team
from coloqo_server.models import Assistant, Installation, LinkRequest, Member, Project, Team
from coloqo_server.naming import new_key, pick_word
from coloqo_server.security import (
    DB,
    Actor,
    ActorDep,
    HumanDep,
    new_token,
    now,
    token_hash,
)

router = APIRouter(tags=["assistants"])

LINK_MINUTES = 10
"""How long a link to choose a project's Team works."""

WORD = re.compile(r"^[a-z][a-z0-9-]{0,31}$")
"""An Assistant's word: a lowercase Latin letter first, then letters, digits and hyphens."""


class AssistantIn(BaseModel):
    """A session registering its Assistant (decision 0024).

    Attributes:
        project_key: SHA-256 of the project path; the path itself stays on the computer.
        project_name: Short project name for the Assistant's shown name.
        team: The Team's slug named by the project's ``.coloqo.json``; links an unlinked
            project whose person is a member of it, and never overrides a link (decision 0020).
        team_id: The Team's id from a ``.coloqo.json`` written before slugs; understood for one
            more release (decision 0025).
        session_id: The Claude Code session id; without it the project has one Assistant.
    """

    project_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    project_name: str = Field(min_length=1, max_length=60)
    team: str | None = Field(default=None, max_length=40)
    team_id: int | None = None
    session_id: str | None = Field(default=None, max_length=100)


class AssistantSelf(BaseModel):
    """The registered Assistant, as its session knows itself.

    Attributes:
        key: Its key, sent in ``X-Coloqo-Assistant``.
        name: Shown name, ``alice · web-app · vega``.
        word: Its word.
        project: The project folder's name.
        project_key: The project's public key, shared by its sessions.
        team: The slug of the Team the project is linked to; ``None`` while unlinked.
        team_name: That Team's name.
    """

    key: str
    name: str
    word: str
    project: str
    project_key: str
    team: str | None = None
    team_name: str | None = None


class WordIn(BaseModel):
    """A new word for an Assistant.

    Attributes:
        word: Lowercase Latin letters, digits and hyphens, a letter first, up to 32.
    """

    word: str

    @field_validator("word")
    @classmethod
    def _word(cls, value: str) -> str:
        """Check the word.

        Args:
            value: The word asked for.

        Raises:
            ValueError: Not a letter first and then letters, digits and hyphens, up to 32.
        """
        value = value.strip().lower()
        if not WORD.match(value):
            raise ValueError("A word is a Latin letter, then letters, digits or hyphens, up to 32")
        return value


class ProjectOut(BaseModel):
    """One of the person's projects with its shown sessions, as their settings list it.

    Attributes:
        key: The project's public key.
        name: The folder's name.
        installation: Name of the computer.
        team: The slug of the Team it is linked to, if any.
        team_name: That Team's name.
        assistants: Its shown Assistants: online, or offline for less than ``SHOWN``.
        last_seen_at: The last request of any of its Assistants.
    """

    key: str
    name: str
    installation: str
    team: str | None
    team_name: str | None
    assistants: list[AssistantOut]
    last_seen_at: datetime | None


class TeamChoice(BaseModel):
    """The Team a project is linked to, chosen by its person in the web.

    Attributes:
        team: The Team's slug; ``None`` unlinks.
    """

    team: str | None


class LinkOut(BaseModel):
    """A one-time link where the person chooses the project's Team.

    Attributes:
        url: The page to open.
        expires_at: After this it does not work.
    """

    url: str
    expires_at: datetime


class LinkPage(BaseModel):
    """What a link to choose a project's Team shows.

    Attributes:
        project: The folder's name.
        installation: Name of the computer.
        team: The slug of the Team it is linked to now, if any.
        team_name: That Team's name.
        valid: The link can still be used.
    """

    project: str
    installation: str
    team: str | None
    team_name: str | None
    valid: bool


def assistant_name(pseudonym: str | None, project: str, word: str) -> str:
    """Return an Assistant's shown name.

    Args:
        pseudonym: Its person's name.
        project: The project folder's name.
        word: Its word.
    """
    return f"{pseudonym} · {project} · {word}"


async def busy_words(db: AsyncSession, project_id: int, but: int | None = None) -> set[str]:
    """Return the words of a project's live Assistants.

    Args:
        db: Database session.
        project_id: The project.
        but: An Assistant whose word does not count.
    """
    return set(
        await db.scalars(
            select(Assistant.word).where(
                Assistant.project_id == project_id,
                Assistant.id != (but or 0),
                Assistant.last_seen_at > now() - LIVE,
            )
        )
    )


async def register(
    db: AsyncSession,
    actor: Actor,
    project_key: str,
    project_name: str,
    team_id: int | None,
    session_id: str | None,
) -> tuple[Assistant, Project]:
    """Register a session's Assistant, and its project on first sight (decision 0024).

    The project's Team named by its ``.coloqo.json`` links it when it is not linked yet and the
    person is a member of that Team; otherwise it is ignored, so a file never overrides the
    person's choice (decision 0020).

    Args:
        db: Database session.
        actor: The plugin.
        project_key: Hash of the project path.
        project_name: The folder's name.
        team_id: The Team the project's ``.coloqo.json`` names, if any.
        session_id: The Claude Code session; ``None`` for a plugin without sessions.

    Raises:
        HTTPException: 403 for a web session: only the plugin registers Assistants.
    """
    if actor.installation is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the plugin registers Assistants")
    name = project_name.strip()[:60]
    await db.execute(
        insert(Project)
        .values(
            key=new_key(),
            user_id=actor.user.id,
            installation_id=actor.installation.id,
            project_key=project_key,
            name=name,
        )
        .on_conflict_do_update(
            index_elements=["installation_id", "project_key"], set_={"name": name}
        )
    )
    project = await db.scalar(
        select(Project).where(
            Project.installation_id == actor.installation.id, Project.project_key == project_key
        )
    )
    assert project is not None
    if (
        team_id is not None
        and project.team_id is None
        and await db.get(Member, (team_id, actor.user.id)) is not None
    ):
        project.team_id = team_id
    session_key = hashlib.sha256(session_id.encode()).hexdigest() if session_id else ""
    assistant = await db.scalar(
        select(Assistant).where(
            Assistant.project_id == project.id, Assistant.session_key == session_key
        )
    )
    if assistant is None:
        word = pick_word(await busy_words(db, project.id))
        await db.execute(
            insert(Assistant)
            .values(
                key=new_key(),
                user_id=actor.user.id,
                installation_id=actor.installation.id,
                project_id=project.id,
                session_key=session_key,
                session_id=session_id,
                word=word,
                name=assistant_name(actor.user.pseudonym, project.name, word),
                last_seen_at=now(),
            )
            .on_conflict_do_nothing(index_elements=["project_id", "session_key"])
        )
        assistant = await db.scalar(
            select(Assistant).where(
                Assistant.project_id == project.id, Assistant.session_key == session_key
            )
        )
        assert assistant is not None
    assistant.name = assistant_name(actor.user.pseudonym, project.name, assistant.word)
    assistant.last_seen_at = now()
    await db.commit()
    return assistant, project


async def self_view(db: AsyncSession, assistant: Assistant, project: Project) -> AssistantSelf:
    """Build the view an Assistant's session has of itself.

    Args:
        db: Database session.
        assistant: The Assistant.
        project: Its project.
    """
    team = await db.get(Team, project.team_id) if project.team_id else None
    return AssistantSelf(
        key=assistant.key,
        name=assistant.name,
        word=assistant.word,
        project=project.name,
        project_key=project.key,
        team=team.slug if team else None,
        team_name=team.name if team else None,
    )


@router.post("/assistant")
async def register_assistant(body: AssistantIn, actor: ActorDep, db: DB) -> AssistantSelf:
    """Register the calling session's Assistant (decisions 0003, 0024).

    One Assistant per project and Claude Code session: the plugin's tools, hooks and watch in
    that session act as it.

    Args:
        body: The project and the session.
        actor: The plugin.
        db: Database session.

    Raises:
        HTTPException: 403 for a web session: only the plugin registers Assistants.
    """
    team = await find_team(db, body.team) if body.team else None
    team_id = team.id if team else body.team_id
    assistant, project = await register(
        db, actor, body.project_key, body.project_name, team_id, body.session_id
    )
    return await self_view(db, assistant, project)


async def _own(db: AsyncSession, key: str, actor: Actor) -> tuple[Assistant, Project]:
    """Return one of the person's Assistants by key; from the plugin, only its own session.

    Args:
        db: Database session.
        key: The Assistant's key.
        actor: Its person in the web, or the session itself.

    Raises:
        HTTPException: 404 when it is not the caller's.
    """
    assistant = await db.scalar(select(Assistant).where(Assistant.key == key))
    if (
        assistant is None
        or assistant.user_id != actor.user.id
        or (
            actor.installation is not None
            and (actor.assistant is None or actor.assistant.id != assistant.id)
        )
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such Assistant")
    project = await db.get(Project, assistant.project_id)
    assert project is not None
    return assistant, project


@router.get("/assistant/{key}")
async def get_assistant(key: str, actor: ActorDep, db: DB) -> AssistantSelf:
    """Return an Assistant to its person, or to its own session; the plugin waits here for a
    link to be chosen, and the watch calls it every 20 seconds to show its session runs
    (decision 0029).

    Args:
        key: The Assistant's key.
        actor: Its person in the web, or the session itself.
        db: Database session.

    Raises:
        HTTPException: 404 when it is not the caller's.
    """
    assistant, project = await _own(db, key, actor)
    return await self_view(db, assistant, project)


@router.patch("/assistant/{key}")
async def rename_assistant(key: str, body: WordIn, actor: ActorDep, db: DB) -> AssistantSelf:
    """Give an Assistant another word; by its person in the web or by the session (0024).

    Args:
        key: The Assistant's key.
        body: The new word.
        actor: Its person in the web, or the session itself.
        db: Database session.

    Raises:
        HTTPException: 404 when it is not the caller's; 409 when a live Assistant of the same
            project has the word.
    """
    assistant, project = await _own(db, key, actor)
    if body.word != assistant.word:
        if body.word in await busy_words(db, project.id, but=assistant.id):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Another live session of {project.name} is called {body.word!r}",
            )
        assistant.word = body.word
        assistant.name = assistant_name(actor.user.pseudonym, project.name, body.word)
        await db.commit()
    return await self_view(db, assistant, project)


async def project_outs(db: AsyncSession, actor: Actor, projects: list[Project]) -> list[ProjectOut]:
    """Describe projects for their person: computer, Team and live sessions.

    Args:
        db: Database session.
        actor: The person.
        projects: The projects.
    """
    if not projects:
        return []
    ids = [p.id for p in projects]
    installations = {
        i.id: i.name
        for i in await db.scalars(
            select(Installation).where(Installation.id.in_({p.installation_id for p in projects}))
        )
    }
    teams = {
        t.id: t
        for t in await db.scalars(
            select(Team).where(Team.id.in_({p.team_id for p in projects} - {None}))
        )
    }
    assistants = list(
        await db.scalars(
            select(Assistant)
            .where(Assistant.project_id.in_(ids))
            .order_by(Assistant.last_seen_at.desc().nulls_last())
        )
    )
    result = []
    for project in projects:
        own = [a for a in assistants if a.project_id == project.id]
        team = teams.get(project.team_id or 0)
        result.append(
            ProjectOut(
                key=project.key,
                name=project.name,
                installation=installations.get(project.installation_id, ""),
                team=team.slug if team else None,
                team_name=team.name if team else None,
                assistants=[
                    assistant_out(a, project, actor)
                    for a in own
                    if a.last_seen_at and a.last_seen_at > now() - SHOWN
                ],
                last_seen_at=own[0].last_seen_at if own else None,
            )
        )
    never = datetime.min.replace(tzinfo=UTC)
    return sorted(result, key=lambda p: p.last_seen_at or never, reverse=True)


@router.get("/project")
async def list_projects(actor: HumanDep, db: DB) -> list[ProjectOut]:
    """List the person's projects on computers not revoked, with their Teams and live sessions.

    Args:
        actor: The logged-in human.
        db: Database session.
    """
    projects = list(
        await db.scalars(
            select(Project)
            .join(Installation, Installation.id == Project.installation_id)
            .where(Project.user_id == actor.user.id, Installation.revoked_at.is_(None))
        )
    )
    return await project_outs(db, actor, projects)


async def choose_team(db: AsyncSession, actor: Actor, project: Project, team: str | None) -> None:
    """Link a project to one of the person's Teams, or unlink it.

    Only the person, from the web: the model in a session cannot move itself to another Team
    (decision 0020).

    Args:
        db: Database session.
        actor: The logged-in human.
        project: The project.
        team: The Team's slug, or ``None``.

    Raises:
        HTTPException: 404 when the person is not in the Team.
    """
    if team is None:
        project.team_id = None
        return
    found = await find_team(db, team)
    if found is None or await db.get(Member, (found.id, actor.user.id)) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such Team")
    project.team_id = found.id


@router.put("/project/{key}/team")
async def link_project(key: str, body: TeamChoice, actor: HumanDep, db: DB) -> ProjectOut:
    """Link one of the person's projects to a Team, or unlink it, from the settings.

    Args:
        key: The project's key.
        body: The Team, or ``None``.
        actor: The logged-in human.
        db: Database session.

    Raises:
        HTTPException: 404 when the project is not theirs or they are not in the Team.
    """
    project = await db.scalar(select(Project).where(Project.key == key))
    if project is None or project.user_id != actor.user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such project")
    await choose_team(db, actor, project, body.team)
    await db.commit()
    (out,) = await project_outs(db, actor, [project])
    return out


@router.post("/link", status_code=status.HTTP_201_CREATED)
async def request_link(request: Request, actor: ActorDep, db: DB) -> LinkOut:
    """Make a one-time link where the session's person chooses the project's Team (0025).

    Args:
        request: The incoming request.
        actor: The session's Assistant.
        db: Database session.

    Raises:
        HTTPException: 403 without an Assistant.
    """
    if actor.assistant is None or actor.project is None or actor.installation is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only a session's Assistant asks to link")
    token = new_token()
    link = LinkRequest(
        token_hash=token_hash(token),
        project_id=actor.project.id,
        installation_id=actor.installation.id,
        expires_at=now() + timedelta(minutes=LINK_MINUTES),
    )
    db.add(link)
    await db.commit()
    return LinkOut(
        url=f"{request.app.state.settings.public_url}/link/{token}", expires_at=link.expires_at
    )


async def _link(db: AsyncSession, token: str, actor: Actor) -> tuple[LinkRequest, Project]:
    """Find a link of the person by the token from its address.

    Args:
        db: Database session.
        token: Token from the link.
        actor: The logged-in human.

    Raises:
        HTTPException: 404 when there is no such link of theirs.
    """
    link = await db.scalar(select(LinkRequest).where(LinkRequest.token_hash == token_hash(token)))
    project = await db.get(Project, link.project_id) if link else None
    if link is None or project is None or project.user_id != actor.user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such link")
    return link, project


@router.get("/link/{token}")
async def show_link(token: str, actor: HumanDep, db: DB) -> LinkPage:
    """Show what a link to choose a project's Team is about.

    Args:
        token: Token from the link.
        actor: The logged-in human.
        db: Database session.

    Raises:
        HTTPException: 404 when there is no such link of theirs.
    """
    link, project = await _link(db, token, actor)
    installation = await db.get(Installation, link.installation_id)
    team = await db.get(Team, project.team_id) if project.team_id else None
    return LinkPage(
        project=project.name,
        installation=installation.name if installation else "",
        team=team.slug if team else None,
        team_name=team.name if team else None,
        valid=link.used_at is None and link.expires_at > now(),
    )


@router.put("/link/{token}")
async def use_link(token: str, body: TeamChoice, actor: HumanDep, db: DB) -> LinkPage:
    """Choose the project's Team by a one-time link; the link stops working.

    Args:
        token: Token from the link.
        body: The Team, or ``None`` to unlink.
        actor: The logged-in human.
        db: Database session.

    Raises:
        HTTPException: 404 when there is no such link of theirs or they are not in the Team;
            410 when it is used or expired.
    """
    link, project = await _link(db, token, actor)
    if link.used_at is not None or link.expires_at <= now():
        raise HTTPException(status.HTTP_410_GONE, "This link is used or expired")
    await choose_team(db, actor, project, body.team)
    link.used_at = now()
    await db.commit()
    return await show_link(token, actor, db)
