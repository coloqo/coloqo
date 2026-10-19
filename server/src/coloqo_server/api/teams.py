"""Teams, their Members, invitations and Areas."""

from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from coloqo_server.models import (
    Area,
    Assistant,
    Invite,
    Member,
    Role,
    Team,
    Topic,
    TopicStatus,
    User,
)
from coloqo_server.security import (
    DB,
    ActorDep,
    HumanDep,
    new_token,
    now,
    require_reader,
    token_hash,
)

router = APIRouter(tags=["teams"])

INVITE_DAYS = 7


class TeamIn(BaseModel):
    """A new Team.

    Attributes:
        name: Shown name.
    """

    name: str = Field(min_length=1, max_length=100)


class TeamPatch(BaseModel):
    """Changes to a Team's settings.

    Attributes:
        name: New name.
        turn_limit: Assistants' turns in a Topic without a human before it waits (0007).
    """

    name: str | None = Field(default=None, min_length=1, max_length=100)
    turn_limit: int | None = Field(default=None, ge=1, le=100)


class TeamOut(BaseModel):
    """A Team as one of its Members sees it.

    Attributes:
        id: Identifier.
        name: Shown name.
        role: The caller's role.
        turn_limit: Assistants' turns without a human before a Topic waits.
        created_at: Creation time.
    """

    id: int
    name: str
    role: Role
    turn_limit: int
    created_at: datetime


class AssistantOut(BaseModel):
    """An Assistant of a Member.

    Attributes:
        id: Identifier.
        name: Shown name, ``alice · billing-api``.
        last_seen_at: Its last request.
    """

    id: int
    name: str
    last_seen_at: datetime | None


class MemberOut(BaseModel):
    """A Member of a Team.

    Attributes:
        user_id: User id.
        pseudonym: The name the Team sees.
        role: Owner or member.
        assistants: The Member's Assistants.
    """

    user_id: int
    pseudonym: str | None
    role: Role
    assistants: list[AssistantOut]


class AreaIn(BaseModel):
    """A new Area.

    Attributes:
        name: Shown name, unique in the Team.
        description: What the Area is about; Assistants read it to choose an Area.
    """

    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=2000)


class AreaOut(BaseModel):
    """An Area.

    Attributes:
        id: Identifier.
        team_id: The Team.
        name: Shown name.
        description: What it is about.
        open_topics: Number of open Topics in it.
    """

    id: int
    team_id: int
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
        team_id: The Team's id.
        team_name: The Team.
        valid: The link can still be used.
        already_member: The caller is already in the Team.
    """

    team_id: int
    team_name: str
    valid: bool
    already_member: bool


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


async def ownership(db: AsyncSession, team_id: int, user_id: int) -> Team:
    """Return the Team if the User owns it.

    Args:
        db: Database session.
        team_id: The Team.
        user_id: The User.

    Raises:
        HTTPException: 404 when the User is not in the Team; 403 when not its owner.
    """
    team, member = await membership(db, team_id, user_id)
    if member.role != Role.Owner:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the Team's owner can do this")
    return team


def _team_out(team: Team, role: Role) -> TeamOut:
    """Build the public view of a Team.

    Args:
        team: The Team.
        role: The caller's role in it.
    """
    return TeamOut(
        id=team.id,
        name=team.name,
        role=role,
        turn_limit=team.turn_limit,
        created_at=team.created_at,
    )


async def _areas(db: AsyncSession, team_id: int) -> list[AreaOut]:
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
        AreaOut(
            id=area.id,
            team_id=area.team_id,
            name=area.name,
            description=area.description,
            open_topics=count,
        )
        for area, count in rows
    ]


@router.get("/teams")
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


@router.post("/teams", status_code=status.HTTP_201_CREATED)
async def create_team(body: TeamIn, actor: HumanDep, db: DB) -> TeamOut:
    """Create a Team; its creator owns it.

    Args:
        body: The new Team.
        actor: The logged-in human.
        db: Database session.
    """
    team = Team(name=body.name, turn_limit=10)
    db.add(team)
    await db.flush()
    db.add(Member(team_id=team.id, user_id=actor.user.id, role=Role.Owner))
    await db.commit()
    return _team_out(team, Role.Owner)


@router.get("/teams/{team_id}")
async def get_team(team_id: int, actor: ActorDep, db: DB) -> TeamDetail:
    """Return a Team with its Members, their Assistants linked to it and its Areas.

    Args:
        team_id: The Team.
        actor: The caller.
        db: Database session.

    Raises:
        HTTPException: 404 when the caller is not in the Team; 403 for a plugin request
            without an Assistant.
    """
    require_reader(actor)
    team, own = await membership(db, team_id, actor.user.id)
    member_rows = (
        await db.execute(
            select(Member, User)
            .join(User, User.id == Member.user_id)
            .where(Member.team_id == team_id)
            .order_by(User.pseudonym)
        )
    ).all()
    assistants = (
        await db.scalars(
            select(Assistant)
            .where(
                Assistant.user_id.in_([user.id for _, user in member_rows]),
                Assistant.team_id == team_id,
            )
            .order_by(Assistant.name)
        )
    ).all()
    members = [
        MemberOut(
            user_id=user.id,
            pseudonym=user.pseudonym,
            role=member.role,
            assistants=[
                AssistantOut(id=a.id, name=a.name, last_seen_at=a.last_seen_at)
                for a in assistants
                if a.user_id == user.id
            ],
        )
        for member, user in member_rows
    ]
    return TeamDetail(
        **_team_out(team, own.role).model_dump(), members=members, areas=await _areas(db, team_id)
    )


@router.patch("/teams/{team_id}")
async def update_team(team_id: int, body: TeamPatch, actor: HumanDep, db: DB) -> TeamOut:
    """Change a Team's name or turn limit.

    Args:
        team_id: The Team.
        body: The changes.
        actor: The logged-in owner.
        db: Database session.

    Raises:
        HTTPException: 404 when the caller is not in the Team; 403 when not its owner.
    """
    team = await ownership(db, team_id, actor.user.id)
    if body.name is not None:
        team.name = body.name
    if body.turn_limit is not None:
        team.turn_limit = body.turn_limit
    await db.commit()
    return _team_out(team, Role.Owner)


@router.post("/teams/{team_id}/invites", status_code=status.HTTP_201_CREATED)
async def create_invite(request: Request, team_id: int, actor: HumanDep, db: DB) -> InviteOut:
    """Make a one-time invitation link to the Team.

    Args:
        request: The incoming request.
        team_id: The Team.
        actor: The logged-in owner.
        db: Database session.

    Raises:
        HTTPException: 404 when the caller is not in the Team; 403 when not its owner.
    """
    await ownership(db, team_id, actor.user.id)
    token = new_token()
    invite = Invite(
        team_id=team_id,
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


@router.get("/invites/{token}")
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
        team_id=team.id,
        team_name=team.name,
        valid=invite.used_at is None and invite.expires_at > now(),
        already_member=await db.get(Member, (team.id, actor.user.id)) is not None,
    )


@router.post("/invites/{token}/accept")
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


@router.get("/teams/{team_id}/areas")
async def list_areas(team_id: int, actor: ActorDep, db: DB) -> list[AreaOut]:
    """List a Team's Areas.

    Args:
        team_id: The Team.
        actor: The caller.
        db: Database session.

    Raises:
        HTTPException: 404 when the caller is not in the Team; 403 for a plugin request
            without an Assistant.
    """
    require_reader(actor)
    await membership(db, team_id, actor.user.id)
    return await _areas(db, team_id)


@router.post("/teams/{team_id}/areas", status_code=status.HTTP_201_CREATED)
async def create_area(team_id: int, body: AreaIn, actor: HumanDep, db: DB) -> AreaOut:
    """Create an Area; the owner configures the Team.

    Args:
        team_id: The Team.
        body: The new Area.
        actor: The logged-in owner.
        db: Database session.

    Raises:
        HTTPException: 404 when the caller is not in the Team; 403 when not its owner;
            409 when the name is taken in the Team.
    """
    await ownership(db, team_id, actor.user.id)
    area = Area(team_id=team_id, name=body.name, description=body.description)
    db.add(area)
    try:
        await db.commit()
    except IntegrityError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, "An Area with this name exists") from error
    return AreaOut(
        id=area.id,
        team_id=team_id,
        name=area.name,
        description=area.description,
        open_topics=0,
    )


@router.patch("/areas/{area_id}")
async def update_area(area_id: int, body: AreaIn, actor: HumanDep, db: DB) -> AreaOut:
    """Rename an Area or change its description.

    Args:
        area_id: The Area.
        body: New name and description.
        actor: The logged-in owner.
        db: Database session.

    Raises:
        HTTPException: 404 when there is no such Area for the caller; 403 when not the
            owner; 409 when the name is taken.
    """
    area = await db.get(Area, area_id)
    if area is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such Area")
    await ownership(db, area.team_id, actor.user.id)
    area.name = body.name
    area.description = body.description
    try:
        await db.commit()
    except IntegrityError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, "An Area with this name exists") from error
    areas = await _areas(db, area.team_id)
    return next(a for a in areas if a.id == area_id)
