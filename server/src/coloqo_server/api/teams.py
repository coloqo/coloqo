"""Teams, their Members, invitations and Areas, by slug (decisions 0024, 0025)."""

from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from coloqo_server.api.avatars import avatar_url
from coloqo_server.models import (
    Area,
    Assistant,
    FormerAreaSlug,
    FormerTeamSlug,
    Invite,
    Member,
    Project,
    Role,
    Team,
    Topic,
    TopicStatus,
    User,
)
from coloqo_server.naming import SLUG, numbered, slugify
from coloqo_server.security import (
    DB,
    Actor,
    ActorDep,
    HumanDep,
    new_token,
    now,
    require_reader,
    token_hash,
)

router = APIRouter(tags=["teams"])

INVITE_DAYS = 7

LIVE = timedelta(hours=24)
"""An Assistant seen this recently keeps its word: a new session of its project gets another."""

ONLINE = timedelta(seconds=60)
"""An Assistant whose session made a request this recently is online (decision 0029).

The watch of a running session makes one at each heartbeat of its stream, about every 15
seconds, so a minute covers a couple of missed ones and a restart of the server.
"""

SHOWN = timedelta(minutes=20)
"""An Assistant offline longer than this is forgotten: no list shows it (decision 0029)."""


def online(assistant: Assistant, moment: datetime | None = None) -> bool:
    """Whether an Assistant's session runs: it made a request within ``ONLINE``.

    Args:
        assistant: The Assistant.
        moment: When to judge; now when omitted.
    """
    seen = assistant.last_seen_at
    return seen is not None and seen > (moment or now()) - ONLINE


def _slug(value: str | None) -> str | None:
    """Check a slug given by a person.

    Args:
        value: The slug, or ``None`` when not given.

    Raises:
        ValueError: Not lowercase Latin letters, digits and inner hyphens, 1 to 40 long.
    """
    if value is None:
        return None
    value = value.strip()
    if not SLUG.match(value):
        raise ValueError(
            "A slug is 1 to 40 lowercase Latin letters, digits and hyphens, not at the ends"
        )
    return value


class TeamIn(BaseModel):
    """A new Team.

    Attributes:
        name: Shown name.
        slug: Its address; offered from the name when omitted.
    """

    name: str = Field(min_length=1, max_length=100)
    slug: str | None = None

    _check_slug = field_validator("slug")(_slug)


class TeamPatch(BaseModel):
    """Changes to a Team's settings.

    Attributes:
        name: New name.
        slug: New address; the former one keeps leading to the Team.
        turn_limit: Assistants' turns in a Topic without a human before it waits (0007).
    """

    name: str | None = Field(default=None, min_length=1, max_length=100)
    slug: str | None = None
    turn_limit: int | None = Field(default=None, ge=1, le=100)

    _check_slug = field_validator("slug")(_slug)


class TeamOut(BaseModel):
    """A Team as one of its Members sees it.

    Attributes:
        slug: Its address, ``acme``.
        name: Shown name.
        role: The caller's role.
        turn_limit: Assistants' turns without a human before a Topic waits.
        created_at: Creation time.
    """

    slug: str
    name: str
    role: Role
    turn_limit: int
    created_at: datetime


class AssistantOut(BaseModel):
    """A shown Assistant of a Member: online, or offline for less than ``SHOWN`` (0024, 0029).

    Attributes:
        key: Its public key.
        name: Shown name, ``alice · billing-api · vega``.
        word: Its own word, ``vega``.
        project: The project folder's name.
        last_seen_at: Its last request.
        online: Its session runs now (decision 0029).
        session_id: The Claude Code session id; only its owner gets it.
    """

    key: str
    name: str
    word: str
    project: str
    last_seen_at: datetime | None
    online: bool = False
    session_id: str | None = None


class MemberOut(BaseModel):
    """A Member of a Team.

    Attributes:
        pseudonym: The name the Team sees.
        role: Owner or member.
        assistants: The Member's shown Assistants whose projects are linked to this Team.
        avatar: Where their avatar is served; ``None`` shows their initials.
    """

    pseudonym: str | None
    role: Role
    assistants: list[AssistantOut]
    avatar: str | None = None


class AreaIn(BaseModel):
    """A new Area.

    Attributes:
        name: Shown name, unique in the Team.
        description: What the Area is about; Assistants read it to choose an Area.
        slug: Its address in the Team; offered from the name when omitted.
    """

    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=2000)
    slug: str | None = None

    _check_slug = field_validator("slug")(_slug)


class AreaPatch(BaseModel):
    """Changes to an Area.

    Attributes:
        name: New name.
        description: New description.
        slug: New address; the former one keeps leading to the Area.
    """

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    slug: str | None = None

    _check_slug = field_validator("slug")(_slug)


class AreaOut(BaseModel):
    """An Area.

    Attributes:
        slug: Its address in the Team, ``releases``.
        name: Shown name.
        description: What it is about.
        open_topics: Number of open Topics in it.
    """

    slug: str
    name: str
    description: str
    open_topics: int


class TeamDetail(TeamOut):
    """A Team with its Members and Areas.

    Attributes:
        members: The Members.
        areas: The Areas.
    """

    members: list[MemberOut]
    areas: list[AreaOut]


class InviteOut(BaseModel):
    """A one-time invitation link (decision 0014).

    Attributes:
        url: The link to pass on personally.
        expires_at: After this it does not work.
    """

    url: str
    expires_at: datetime


class InvitePreview(BaseModel):
    """What an invitation link leads to.

    Attributes:
        team: The Team's slug.
        team_name: The Team.
        valid: The link can still be used.
        already_member: The caller is already in the Team.
    """

    team: str
    team_name: str
    valid: bool
    already_member: bool


async def find_team(db: AsyncSession, slug: str) -> Team | None:
    """Return the Team with this slug or a former one.

    Args:
        db: Database session.
        slug: Current or former slug.
    """
    team = await db.scalar(select(Team).where(Team.slug == slug))
    if team is None:
        former = await db.get(FormerTeamSlug, slug)
        team = await db.get(Team, former.team_id) if former else None
    return team


async def membership(db: AsyncSession, team_id: int, user_id: int) -> tuple[Team, Member]:
    """Return the Team and the User's membership in it.

    Args:
        db: Database session.
        team_id: The Team.
        user_id: The User.

    Raises:
        HTTPException: 404 when there is no such Team or the User is not in it.
    """
    member = await db.get(Member, (team_id, user_id))
    team = await db.get(Team, team_id) if member else None
    if member is None or team is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such Team")
    return team, member


async def team_for(db: AsyncSession, slug: str, user_id: int) -> tuple[Team, Member]:
    """Return a Team of the User by its current or former slug, and their membership.

    Args:
        db: Database session.
        slug: The Team's slug.
        user_id: The User.

    Raises:
        HTTPException: 404 when there is no such Team or the User is not in it.
    """
    team = await find_team(db, slug)
    if team is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such Team")
    return await membership(db, team.id, user_id)


async def owned(db: AsyncSession, slug: str, user_id: int) -> Team:
    """Return a Team by slug if the User owns it.

    Args:
        db: Database session.
        slug: The Team's slug.
        user_id: The User.

    Raises:
        HTTPException: 404 when the User is not in the Team; 403 when not its owner.
    """
    team, member = await team_for(db, slug, user_id)
    if member.role != Role.Owner:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the Team's owner can do this")
    return team


async def find_area(db: AsyncSession, team_id: int, slug: str) -> Area | None:
    """Return a Team's Area with this slug or a former one.

    Args:
        db: Database session.
        team_id: The Team.
        slug: Current or former slug of the Area.
    """
    area = await db.scalar(select(Area).where(Area.team_id == team_id, Area.slug == slug))
    if area is None:
        former = await db.get(FormerAreaSlug, (team_id, slug))
        area = await db.get(Area, former.area_id) if former else None
    return area


async def _taken_team_slugs(db: AsyncSession, but: int | None = None) -> set[str]:
    """Return the slugs no other Team may take: current and former ones.

    Args:
        db: Database session.
        but: A Team whose own slugs do not count.
    """
    current = select(Team.slug).where(Team.id != (but or 0))
    former = select(FormerTeamSlug.slug).where(FormerTeamSlug.team_id != (but or 0))
    return set(await db.scalars(current)) | set(await db.scalars(former))


async def _taken_area_slugs(db: AsyncSession, team_id: int, but: int | None = None) -> set[str]:
    """Return the slugs no other Area of the Team may take.

    Args:
        db: Database session.
        team_id: The Team.
        but: An Area whose own slugs do not count.
    """
    current = select(Area.slug).where(Area.team_id == team_id, Area.id != (but or 0))
    former = select(FormerAreaSlug.slug).where(
        FormerAreaSlug.team_id == team_id, FormerAreaSlug.area_id != (but or 0)
    )
    return set(await db.scalars(current)) | set(await db.scalars(former))


def _team_out(team: Team, role: Role) -> TeamOut:
    """Build the public view of a Team.

    Args:
        team: The Team.
        role: The caller's role in it.
    """
    return TeamOut(
        slug=team.slug,
        name=team.name,
        role=role,
        turn_limit=team.turn_limit,
        created_at=team.created_at,
    )


async def areas_of(db: AsyncSession, team_id: int) -> list[AreaOut]:
    """Return a Team's Areas with their open Topic counts.

    Args:
        db: Database session.
        team_id: The Team.
    """
    open_counts = (
        select(Topic.area_id, func.count().label("open"))
        .where(Topic.team_id == team_id, Topic.status == TopicStatus.Open)
        .group_by(Topic.area_id)
        .subquery()
    )
    rows = await db.execute(
        select(Area, func.coalesce(open_counts.c.open, 0))
        .outerjoin(open_counts, open_counts.c.area_id == Area.id)
        .where(Area.team_id == team_id)
        .order_by(Area.name)
    )
    return [
        AreaOut(slug=area.slug, name=area.name, description=area.description, open_topics=count)
        for area, count in rows
    ]


def assistant_out(assistant: Assistant, project: Project, viewer: Actor) -> AssistantOut:
    """Build the view of an Assistant; its session id only for its owner (decision 0024).

    Args:
        assistant: The Assistant.
        project: Its project.
        viewer: Who looks.
    """
    return AssistantOut(
        key=assistant.key,
        name=assistant.name,
        word=assistant.word,
        project=project.name,
        last_seen_at=assistant.last_seen_at,
        online=online(assistant),
        session_id=assistant.session_id if assistant.user_id == viewer.user.id else None,
    )


@router.get("/team")
async def list_teams(actor: ActorDep, db: DB) -> list[TeamOut]:
    """List the caller's Teams.

    Args:
        actor: The caller.
        db: Database session.

    Raises:
        HTTPException: 403 for a plugin request without an Assistant.
    """
    require_reader(actor)
    rows = await db.execute(
        select(Team, Member.role)
        .join(Member, Member.team_id == Team.id)
        .where(Member.user_id == actor.user.id)
        .order_by(Team.name)
    )
    return [_team_out(team, role) for team, role in rows]


@router.post("/team", status_code=status.HTTP_201_CREATED)
async def create_team(body: TeamIn, actor: HumanDep, db: DB) -> TeamOut:
    """Create a Team; its creator owns it.

    Args:
        body: The new Team.
        actor: The logged-in human.
        db: Database session.

    Raises:
        HTTPException: 409 when the slug asked for is taken.
    """
    taken = await _taken_team_slugs(db)
    if body.slug is not None and body.slug in taken:
        raise HTTPException(status.HTTP_409_CONFLICT, f"The address {body.slug!r} is taken")
    team = Team(
        name=body.name.strip(), slug=body.slug or numbered(slugify(body.name), taken), turn_limit=10
    )
    db.add(team)
    await db.flush()
    db.add(Member(team_id=team.id, user_id=actor.user.id, role=Role.Owner))
    await db.commit()
    return _team_out(team, Role.Owner)


async def team_detail(db: AsyncSession, team: Team, member: Member, actor: Actor) -> TeamDetail:
    """Return a Team with its Members, their live Assistants linked to it, and its Areas.

    Args:
        db: Database session.
        team: The Team.
        member: The caller's membership.
        actor: The caller.
    """
    member_rows = (
        await db.execute(
            select(Member, User)
            .join(User, User.id == Member.user_id)
            .where(Member.team_id == team.id)
            .order_by(User.pseudonym)
        )
    ).all()
    assistants = (
        await db.execute(
            select(Assistant, Project)
            .join(Project, Project.id == Assistant.project_id)
            .where(
                Assistant.user_id.in_([user.id for _, user in member_rows]),
                Project.team_id == team.id,
                Assistant.last_seen_at > now() - SHOWN,
            )
            .order_by(Project.name, Assistant.word)
        )
    ).all()
    members = [
        MemberOut(
            pseudonym=user.pseudonym,
            role=row.role,
            avatar=avatar_url(user),
            assistants=[
                assistant_out(a, project, actor)
                for a, project in assistants
                if a.user_id == user.id
            ],
        )
        for row, user in member_rows
    ]
    return TeamDetail(
        **_team_out(team, member.role).model_dump(),
        members=members,
        areas=await areas_of(db, team.id),
    )


@router.get("/team/{team}")
async def get_team(team: str, actor: ActorDep, db: DB) -> TeamDetail:
    """Return a Team with its Members, their live Assistants linked to it and its Areas.

    A former slug answers too, with the current one in the result.

    Args:
        team: The Team's slug.
        actor: The caller.
        db: Database session.

    Raises:
        HTTPException: 404 when the caller is not in the Team; 403 for a plugin request
            without an Assistant.
    """
    require_reader(actor)
    found, member = await team_for(db, team, actor.user.id)
    return await team_detail(db, found, member, actor)


@router.patch("/team/{team}")
async def update_team(team: str, body: TeamPatch, actor: HumanDep, db: DB) -> TeamOut:
    """Change a Team's name, address or turn limit.

    A changed slug is kept as a former one, so links to the Team keep working; going back to a
    former slug takes it out of the former ones.

    Args:
        team: The Team's slug.
        body: The changes.
        actor: The logged-in owner.
        db: Database session.

    Raises:
        HTTPException: 404 when the caller is not in the Team; 403 when not its owner; 409
            when the new slug is another Team's.
    """
    found = await owned(db, team, actor.user.id)
    if body.slug is not None and body.slug != found.slug:
        if body.slug in await _taken_team_slugs(db, but=found.id):
            raise HTTPException(status.HTTP_409_CONFLICT, f"The address {body.slug!r} is taken")
        former = await db.get(FormerTeamSlug, body.slug)
        if former is not None:
            await db.delete(former)
        db.add(FormerTeamSlug(slug=found.slug, team_id=found.id))
        found.slug = body.slug
    if body.name is not None:
        found.name = body.name.strip()
    if body.turn_limit is not None:
        found.turn_limit = body.turn_limit
    await db.commit()
    return _team_out(found, Role.Owner)


@router.post("/team/{team}/invite", status_code=status.HTTP_201_CREATED)
async def create_invite(request: Request, team: str, actor: HumanDep, db: DB) -> InviteOut:
    """Make a one-time invitation link to the Team.

    Args:
        request: The incoming request.
        team: The Team's slug.
        actor: The logged-in owner.
        db: Database session.

    Raises:
        HTTPException: 404 when the caller is not in the Team; 403 when not its owner.
    """
    found = await owned(db, team, actor.user.id)
    token = new_token()
    invite = Invite(
        team_id=found.id,
        token_hash=token_hash(token),
        created_by=actor.user.id,
        expires_at=now() + timedelta(days=INVITE_DAYS),
    )
    db.add(invite)
    await db.commit()
    return InviteOut(
        url=f"{request.app.state.settings.public_url}/join/{token}", expires_at=invite.expires_at
    )


async def _invite(db: AsyncSession, token: str) -> tuple[Invite, Team]:
    """Find an invitation by the token from its link.

    Args:
        db: Database session.
        token: Token from the link.

    Raises:
        HTTPException: 404 when there is no such invitation.
    """
    invite = await db.scalar(select(Invite).where(Invite.token_hash == token_hash(token)))
    team = await db.get(Team, invite.team_id) if invite else None
    if invite is None or team is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such invitation")
    return invite, team


@router.get("/invite/{token}")
async def preview_invite(token: str, actor: HumanDep, db: DB) -> InvitePreview:
    """Show what an invitation link leads to.

    Args:
        token: Token from the link.
        actor: The logged-in human.
        db: Database session.

    Raises:
        HTTPException: 404 when there is no such invitation.
    """
    invite, team = await _invite(db, token)
    return InvitePreview(
        team=team.slug,
        team_name=team.name,
        valid=invite.used_at is None and invite.expires_at > now(),
        already_member=await db.get(Member, (team.id, actor.user.id)) is not None,
    )


@router.post("/invite/{token}/accept")
async def accept_invite(token: str, actor: HumanDep, db: DB) -> TeamOut:
    """Join a Team by a one-time link.

    Args:
        token: Token from the link.
        actor: The logged-in human.
        db: Database session.

    Raises:
        HTTPException: 404 when there is no such invitation; 410 when it is used or expired.
    """
    invite, team = await _invite(db, token)
    existing = await db.get(Member, (team.id, actor.user.id))
    if existing is not None:
        return _team_out(team, existing.role)
    if invite.used_at is not None or invite.expires_at <= now():
        raise HTTPException(status.HTTP_410_GONE, "This invitation is used or expired")
    invite.used_at = now()
    invite.used_by = actor.user.id
    db.add(Member(team_id=team.id, user_id=actor.user.id, role=Role.Member))
    await db.commit()
    return _team_out(team, Role.Member)


@router.get("/team/{team}/area")
async def list_areas(team: str, actor: ActorDep, db: DB) -> list[AreaOut]:
    """List a Team's Areas.

    Args:
        team: The Team's slug.
        actor: The caller.
        db: Database session.

    Raises:
        HTTPException: 404 when the caller is not in the Team; 403 for a plugin request
            without an Assistant.
    """
    require_reader(actor)
    found, _ = await team_for(db, team, actor.user.id)
    return await areas_of(db, found.id)


@router.post("/team/{team}/area", status_code=status.HTTP_201_CREATED)
async def create_area(team: str, body: AreaIn, actor: HumanDep, db: DB) -> AreaOut:
    """Create an Area; the owner configures the Team.

    Args:
        team: The Team's slug.
        body: The new Area.
        actor: The logged-in owner.
        db: Database session.

    Raises:
        HTTPException: 404 when the caller is not in the Team; 403 when not its owner; 409
            when the name or the slug is taken in the Team.
    """
    found = await owned(db, team, actor.user.id)
    taken = await _taken_area_slugs(db, found.id)
    if body.slug is not None and body.slug in taken:
        raise HTTPException(status.HTTP_409_CONFLICT, f"The address {body.slug!r} is taken")
    area = Area(
        team_id=found.id,
        name=body.name.strip(),
        description=body.description,
        slug=body.slug or numbered(slugify(body.name, "area"), taken),
    )
    db.add(area)
    try:
        await db.commit()
    except IntegrityError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, "An Area with this name exists") from error
    return AreaOut(slug=area.slug, name=area.name, description=area.description, open_topics=0)


@router.patch("/team/{team}/area/{area}")
async def update_area(team: str, area: str, body: AreaPatch, actor: HumanDep, db: DB) -> AreaOut:
    """Rename an Area, change its description or its address.

    Args:
        team: The Team's slug.
        area: The Area's slug.
        body: The changes.
        actor: The logged-in owner.
        db: Database session.

    Raises:
        HTTPException: 404 when there is no such Area for the caller; 403 when not the
            owner; 409 when the name or the slug is taken in the Team.
    """
    found = await owned(db, team, actor.user.id)
    row = await find_area(db, found.id, area)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such Area")
    if body.slug is not None and body.slug != row.slug:
        if body.slug in await _taken_area_slugs(db, found.id, but=row.id):
            raise HTTPException(status.HTTP_409_CONFLICT, f"The address {body.slug!r} is taken")
        former = await db.get(FormerAreaSlug, (found.id, body.slug))
        if former is not None:
            await db.delete(former)
        db.add(FormerAreaSlug(team_id=found.id, slug=row.slug, area_id=row.id))
        row.slug = body.slug
    if body.name is not None:
        row.name = body.name.strip()
    if body.description is not None:
        row.description = body.description
    try:
        await db.commit()
    except IntegrityError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, "An Area with this name exists") from error
    areas = await areas_of(db, found.id)
    return next(a for a in areas if a.slug == row.slug)
