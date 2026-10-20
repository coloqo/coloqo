"""The former paths and shapes, for plugins older than 0.5.0 (decision 0025).

They live one more release, so a member who has not updated the plugin keeps working while the
briefing tells their session to update; the release after removes this module. Everything here
goes through the same operations as the paths of decision 0025; only the addresses (database
ids, ``T-<id>``) and the shapes differ.
"""

from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from coloqo_server.api.assistants import register
from coloqo_server.api.briefing import LEGACY_UPDATE, RULES, UNLINKED_BRIEFING
from coloqo_server.api.files import serve, store_upload
from coloqo_server.api.teams import LIVE, areas_of, membership
from coloqo_server.api.topics import (
    TopicPatch,
    check_topic,
    file_outs,
    hold,
    mark_read,
    message_outs,
    note_stage,
    number_taken,
    open_topic,
    post,
    settle,
    topic_outs,
)
from coloqo_server.models import (
    Area,
    Assistant,
    File,
    Installation,
    Member,
    Message,
    MessageKind,
    Project,
    Team,
    Topic,
    TopicStatus,
    User,
)
from coloqo_server.security import DB, Actor, ActorDep, now, require_reader, require_writer
from coloqo_server.settings import Settings

router = APIRouter(tags=["legacy"], include_in_schema=False)


def legacy_ref(topic_id: int) -> str:
    """Return the reference plugins older than 0.5.0 know a Topic by.

    Args:
        topic_id: The Topic's database id.
    """
    return f"T-{topic_id}"


class LegacyAssistantIn(BaseModel):
    """An Assistant registering, as plugins older than 0.5.0 send it.

    Attributes:
        project_key: SHA-256 of the project path.
        project_name: Short project name.
        team_id: The Team named by the project's ``.coloqo.json``.
    """

    project_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    project_name: str = Field(min_length=1, max_length=60)
    team_id: int | None = None


class LegacyRegistered(BaseModel):
    """The registered Assistant, in the former shape.

    Attributes:
        id: Identifier the plugin sends in ``X-Coloqo-Assistant``.
        name: Shown name.
        team_id: The Team its project is linked to.
        team: That Team's name.
    """

    id: int
    name: str
    team_id: int | None = None
    team: str | None = None


class LegacyOwnAssistant(BaseModel):
    """One of the person's Assistants, in the former shape.

    Attributes:
        id: Identifier.
        name: Shown name.
        installation: Name of the computer.
        team_id: The Team its project is linked to.
        team: That Team's name.
        last_seen_at: Its last request.
    """

    id: int
    name: str
    installation: str
    team_id: int | None
    team: str | None
    last_seen_at: datetime | None


class LegacyFileOut(BaseModel):
    """A file, in the former shape.

    Attributes:
        id: Identifier.
        name: File name.
        size: Size in bytes.
        sha256: Checksum.
        content_type: Media type.
        preview: Shown inline in the web.
        uploaded_by: Pseudonym of the uploader.
        message_number: The Message it is attached to.
        created_at: Upload time.
    """

    id: int
    name: str
    size: int
    sha256: str
    content_type: str
    preview: bool
    uploaded_by: str | None
    message_number: int | None
    created_at: datetime


class LegacyMessageOut(BaseModel):
    """A Message, in the former shape.

    Attributes:
        number: Position in the Topic.
        kind: A turn, a progress note, a stage or closing line.
        author: Pseudonym of its person.
        assistant: Name of its Assistant.
        assistant_id: Its id.
        to: Pseudonym of the addressee.
        to_assistant: Name of the addressed Assistant.
        relayed: The Assistant posted its human's own words.
        reply_to: Number of the Message it answers.
        by_holder: Its Assistant held the Topic.
        system: Written by Coloqo itself.
        body: Markdown text.
        files: Files attached to it.
        created_at: When it was written.
    """

    number: int
    kind: MessageKind
    author: str | None
    assistant: str | None
    assistant_id: int | None
    to: str | None
    to_assistant: str | None
    relayed: bool
    reply_to: int | None
    by_holder: bool
    system: bool
    body: str
    files: list[LegacyFileOut]
    created_at: datetime


class LegacyTopicOut(BaseModel):
    """A Topic, in the former shape.

    Attributes:
        id: Identifier.
        ref: ``T-<id>``.
        team_id: The Team.
        area_id: The Area.
        area: The Area's name.
        title: The question.
        issue: Tracker issue.
        status: Open or closed.
        outcome: How it was settled.
        holder: Name of the holding Assistant.
        holder_assistant_id: Its id.
        created_by: Who opened it.
        last_number: Number of the newest Message.
        turns_since_human: Assistants' turns since a human.
        turn_limit: The Team's limit of such turns.
        unread: Unread Messages.
        addressed: Some unread Message is addressed to the caller.
        created_at: Creation time.
        updated_at: Time of the newest Message.
        closed_at: When it was closed.
        deletes_at: When its conversation will be deleted.
        deleted_at: When its conversation was deleted.
    """

    id: int
    ref: str
    team_id: int
    area_id: int
    area: str
    title: str
    issue: str
    status: TopicStatus
    outcome: str
    holder: str | None
    holder_assistant_id: int | None
    created_by: str | None
    last_number: int
    turns_since_human: int
    turn_limit: int
    unread: int
    addressed: bool
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None
    deletes_at: datetime | None
    deleted_at: datetime | None


class LegacyTopicDetail(LegacyTopicOut):
    """A Topic with Messages, in the former shape.

    Attributes:
        messages: Messages after the requested number.
        files: All files of the Topic.
    """

    messages: list[LegacyMessageOut]
    files: list[LegacyFileOut]


class LegacyTopicIn(BaseModel):
    """A new Topic, as plugins older than 0.5.0 send it.

    Attributes:
        title: The question.
        body: The first Message.
        issue: Tracker issue.
        to: Addressee.
    """

    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=50_000)
    issue: str = Field(default="", max_length=300)
    to: str | None = None


class LegacyMessageIn(BaseModel):
    """A new Message, as plugins older than 0.5.0 send it.

    Attributes:
        number: The number the writer believes is next.
        body: Markdown text.
        kind: ``message`` or ``progress``.
        to: Addressee.
        file_ids: Files to attach, by id.
        as_human: Relays the human's own words.
        reply_to: Number of the Message it answers.
    """

    number: int = Field(ge=1)
    body: str = Field(min_length=1, max_length=50_000)
    kind: MessageKind = MessageKind.Message
    to: str | None = None
    file_ids: list[int] = Field(default_factory=list, max_length=20)
    as_human: bool = False
    reply_to: int | None = Field(default=None, ge=1)

    @field_validator("kind")
    @classmethod
    def _plain_kind(cls, kind: MessageKind) -> MessageKind:
        """Refuse service lines here.

        Args:
            kind: The requested kind.

        Raises:
            ValueError: For a service line.
        """
        if kind not in (MessageKind.Message, MessageKind.Progress):
            raise ValueError("kind is message or progress; a stage goes to /stage")
        return kind


class LegacyStageIn(BaseModel):
    """A stage, as plugins older than 0.5.0 send it.

    Attributes:
        text: One line.
    """

    text: str = Field(min_length=1, max_length=200)


class LegacyReadIn(BaseModel):
    """How far the caller has read.

    Attributes:
        number: Number of the newest Message read.
    """

    number: int = Field(ge=0)


async def legacy_files(
    db: AsyncSession, file_rows: list[File], settings: Settings
) -> list[LegacyFileOut]:
    """Build files in the former shape.

    Args:
        db: Database session.
        file_rows: The files.
        settings: Instance settings.
    """
    views = await file_outs(db, file_rows, settings.preview_max_bytes)
    return [
        LegacyFileOut(id=row.id, **view.model_dump(exclude={"number"}))
        for row, view in zip(file_rows, views, strict=True)
    ]


async def legacy_messages(
    db: AsyncSession, messages: list[Message], file_rows: list[File], settings: Settings
) -> list[LegacyMessageOut]:
    """Build Messages in the former shape; a "taken" line reads as a stage line.

    Args:
        db: Database session.
        messages: The Messages.
        file_rows: The Topic's files.
        settings: Instance settings.
    """
    files = await file_outs(db, file_rows, settings.preview_max_bytes)
    views = await message_outs(db, messages, files, file_rows)
    by_number = {row.number: [f for f in file_rows if f.message_id == row.id] for row in messages}
    old_files = {f.id: f for f in await legacy_files(db, file_rows, settings)}
    return [
        LegacyMessageOut(
            number=view.number,
            kind=MessageKind.Stage if view.kind == MessageKind.Taken else view.kind,
            author=view.author,
            assistant=view.assistant,
            assistant_id=row.author_assistant_id,
            to=view.to,
            to_assistant=view.to_assistant,
            relayed=row.relayed,
            reply_to=view.reply_to,
            by_holder=view.by_holder,
            system=view.system,
            body=view.body,
            files=[old_files[f.id] for f in by_number[row.number]],
            created_at=view.created_at,
        )
        for row, view in zip(messages, views, strict=True)
    ]


async def legacy_topics(
    db: AsyncSession, topics: list[Topic], user_id: int, settings: Settings
) -> list[LegacyTopicOut]:
    """Build Topics in the former shape.

    Args:
        db: Database session.
        topics: The Topics.
        user_id: The caller.
        settings: Instance settings.
    """
    views = await topic_outs(db, topics, user_id, settings.archive_days)
    return [
        LegacyTopicOut(
            id=topic.id,
            ref=legacy_ref(topic.id),
            team_id=topic.team_id,
            area_id=topic.area_id,
            area=view.area_name,
            title=view.title,
            issue=view.issue,
            status=view.status,
            outcome=view.outcome,
            holder=view.holder,
            holder_assistant_id=topic.holder_assistant_id,
            created_by=view.created_by,
            last_number=view.last_number,
            turns_since_human=view.turns_since_human,
            turn_limit=view.turn_limit,
            unread=view.unread,
            addressed=view.addressed,
            created_at=view.created_at,
            updated_at=view.updated_at,
            closed_at=view.closed_at,
            deletes_at=view.deletes_at,
            deleted_at=view.deleted_at,
        )
        for topic, view in zip(topics, views, strict=True)
    ]


async def legacy_briefing(request: Request, db: AsyncSession, actor: Actor) -> dict:
    """Return the briefing in the former shape, with the line asking to update the plugin.

    Args:
        request: The incoming request.
        db: Database session.
        actor: The session's Assistant.
    """
    assert actor.assistant is not None
    settings = request.app.state.settings
    team = await db.get(Team, actor.team_id) if actor.team_id else None
    if team is None:
        return {"text": f"{UNLINKED_BRIEFING}\n\n{LEGACY_UPDATE}", "team_id": None, "team": None}
    held = list(
        await db.scalars(
            select(Topic)
            .where(
                Topic.holder_assistant_id == actor.assistant.id,
                Topic.team_id == team.id,
                Topic.status == TopicStatus.Open,
                Topic.deleted_at.is_(None),
            )
            .order_by(Topic.updated_at.desc())
            .limit(10)
        )
    )
    rules = RULES.format(
        team=team.name,
        user=actor.user.pseudonym,
        other="globex",
        url=settings.public_url,
        slug=team.slug,
    ).split("\n")
    # The last two rules speak of numbers and marks this plugin does not know.
    rules = [line for line in rules if not line.startswith(("- Every reply", "- A Topic here"))]
    lines = [
        LEGACY_UPDATE,
        "",
        f"Coloqo: you are the Assistant «{actor.assistant.name}» of {actor.user.pseudonym} in the "
        f"Team «{team.name}», where the Team's people and assistants work together; everything "
        "you write is signed and the Team sees it.",
        "",
        *rules,
        "",
    ]
    if held:
        lines.append("You hold — continue there and note each stage:")
        for topic in held:
            closes = (topic.updated_at + timedelta(days=settings.idle_close_days)).date()
            lines.append(
                f"- {legacy_ref(topic.id)} «{topic.title}»"
                + (f" [{topic.issue}]" if topic.issue else "")
                + f", closes for inactivity on {closes} if quiet"
            )
    else:
        lines.append("You hold no Topic: open one when you take a task, as above.")
    return {"text": "\n".join(lines), "team_id": team.id, "team": team.name}


async def _topic(
    db: AsyncSession, topic_id: int, actor: Actor, lock: bool = False, write: bool = False
) -> Topic:
    """Return a Topic by its database id, checked against the caller.

    Args:
        db: Database session.
        topic_id: The Topic's id.
        actor: The caller.
        lock: Lock the row.
        write: The caller is about to change it.

    Raises:
        HTTPException: 404 when there is no such Topic in the caller's Teams; 403 when the
            caller may not write there; 410 to write into a deleted Topic.
    """
    require_reader(actor)
    query = select(Topic).where(Topic.id == topic_id)
    topic = await db.scalar(query.with_for_update() if lock else query)
    return await check_topic(db, topic, actor, legacy_ref(topic_id), write)


async def _detail(
    request: Request, db: AsyncSession, actor: Actor, topic: Topic, messages: list[Message]
) -> LegacyTopicDetail:
    """Build a Topic with Messages in the former shape.

    Args:
        request: The incoming request.
        db: Database session.
        actor: The caller.
        topic: The Topic.
        messages: Its Messages to show.
    """
    settings = request.app.state.settings
    file_rows = list(
        await db.scalars(select(File).where(File.topic_id == topic.id).order_by(File.id))
    )
    (summary,) = await legacy_topics(db, [topic], actor.user.id, settings)
    return LegacyTopicDetail(
        **summary.model_dump(),
        messages=await legacy_messages(db, messages, file_rows, settings),
        files=await legacy_files(db, file_rows, settings),
    )


async def _own_out(db: AsyncSession, assistant: Assistant) -> LegacyOwnAssistant:
    """Build one of the person's Assistants in the former shape.

    Args:
        db: Database session.
        assistant: The Assistant.
    """
    project = await db.get(Project, assistant.project_id)
    installation = await db.get(Installation, assistant.installation_id)
    team = await db.get(Team, project.team_id) if project and project.team_id else None
    return LegacyOwnAssistant(
        id=assistant.id,
        name=assistant.name,
        installation=installation.name if installation else "",
        team_id=team.id if team else None,
        team=team.name if team else None,
        last_seen_at=assistant.last_seen_at,
    )


@router.post("/assistants")
async def register_assistant(body: LegacyAssistantIn, actor: ActorDep, db: DB) -> LegacyRegistered:
    """Register the Assistant of a plugin older than 0.5.0: one per project, no sessions.

    Args:
        body: The project.
        actor: The plugin.
        db: Database session.

    Raises:
        HTTPException: 403 for a web session.
    """
    assistant, project = await register(
        db, actor, body.project_key, body.project_name, body.team_id, None
    )
    team = await db.get(Team, project.team_id) if project.team_id else None
    return LegacyRegistered(
        id=assistant.id,
        name=assistant.name,
        team_id=team.id if team else None,
        team=team.name if team else None,
    )


@router.get("/assistants/{assistant_id}")
async def get_own_assistant(assistant_id: int, actor: ActorDep, db: DB) -> LegacyOwnAssistant:
    """Return the calling plugin's Assistant; the plugin waits here for a link.

    Args:
        assistant_id: The Assistant.
        actor: The plugin.
        db: Database session.

    Raises:
        HTTPException: 404 when it is not the caller's.
    """
    assistant = await db.get(Assistant, assistant_id)
    if (
        assistant is None
        or assistant.user_id != actor.user.id
        or (actor.installation is not None and assistant.installation_id != actor.installation.id)
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such Assistant")
    return await _own_out(db, assistant)


@router.get("/teams")
async def list_teams(actor: ActorDep, db: DB) -> list[dict]:
    """List the caller's Teams, in the former shape.

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
    return [
        {
            "id": team.id,
            "name": team.name,
            "role": role.value,
            "turn_limit": team.turn_limit,
            "created_at": team.created_at,
        }
        for team, role in rows
    ]


@router.get("/teams/{team_id}")
async def get_team(team_id: int, actor: ActorDep, db: DB) -> dict:
    """Return a Team with Members, live Assistants and Areas, in the former shape.

    Args:
        team_id: The Team.
        actor: The caller.
        db: Database session.

    Raises:
        HTTPException: 404 when the caller is not in the Team; 403 without an Assistant.
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
    assistants = list(
        await db.scalars(
            select(Assistant)
            .join(Project, Project.id == Assistant.project_id)
            .where(Project.team_id == team_id, Assistant.last_seen_at > now() - LIVE)
            .order_by(Assistant.name)
        )
    )
    areas = {a.slug: a.id for a in await db.scalars(select(Area).where(Area.team_id == team_id))}
    return {
        "id": team.id,
        "name": team.name,
        "role": own.role.value,
        "turn_limit": team.turn_limit,
        "created_at": team.created_at,
        "members": [
            {
                "user_id": user.id,
                "pseudonym": user.pseudonym,
                "role": member.role.value,
                "avatar": None,
                "assistants": [
                    {"id": a.id, "name": a.name, "last_seen_at": a.last_seen_at}
                    for a in assistants
                    if a.user_id == user.id
                ],
            }
            for member, user in member_rows
        ],
        "areas": [
            {
                "id": areas[a.slug],
                "team_id": team.id,
                "name": a.name,
                "description": a.description,
                "open_topics": a.open_topics,
            }
            for a in await areas_of(db, team_id)
        ],
    }


@router.get("/teams/{team_id}/topics")
async def list_topics(
    request: Request,
    team_id: int,
    actor: ActorDep,
    db: DB,
    area_id: Annotated[int | None, Query()] = None,
    status_filter: Annotated[TopicStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[LegacyTopicOut]:
    """List a Team's Topics, in the former shape.

    Args:
        request: The incoming request.
        team_id: The Team.
        actor: The caller.
        db: Database session.
        area_id: Only this Area.
        status_filter: Only open or only closed.
        limit: At most this many.

    Raises:
        HTTPException: 404 when the caller is not in the Team; 403 without an Assistant.
    """
    require_reader(actor)
    await membership(db, team_id, actor.user.id)
    query = select(Topic).where(Topic.team_id == team_id, Topic.deleted_at.is_(None))
    if area_id is not None:
        query = query.where(Topic.area_id == area_id)
    if status_filter is not None:
        query = query.where(Topic.status == status_filter)
    topics = list(await db.scalars(query.order_by(Topic.updated_at.desc()).limit(limit)))
    return await legacy_topics(db, topics, actor.user.id, request.app.state.settings)


@router.post("/areas/{area_id}/topics", status_code=status.HTTP_201_CREATED)
async def create_topic(
    request: Request, area_id: int, body: LegacyTopicIn, actor: ActorDep, db: DB
) -> LegacyTopicDetail:
    """Open a Topic, in the former shape.

    Args:
        request: The incoming request.
        area_id: The Area.
        body: Title and first Message.
        actor: The caller.
        db: Database session.

    Raises:
        HTTPException: 404 when there is no such Area for the caller; 403 when the caller may
            not write there; 422 for an unknown addressee.
    """
    require_reader(actor)
    area = await db.get(Area, area_id)
    if area is None or await db.get(Member, (area.team_id, actor.user.id)) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such Area")
    await require_writer(db, actor, area.team_id)
    topic, recipients = await open_topic(
        db, actor, area, body.title, body.body, body.issue, body.to, False
    )
    await db.commit()
    request.app.state.bus.wake(recipients)
    messages = list(await db.scalars(select(Message).where(Message.topic_id == topic.id)))
    return await _detail(request, db, actor, topic, messages)


@router.get("/topics/{topic_id}")
async def read_topic(
    request: Request,
    topic_id: int,
    actor: ActorDep,
    db: DB,
    after: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> LegacyTopicDetail:
    """Return a Topic with its Messages after a number, in the former shape.

    Args:
        request: The incoming request.
        topic_id: The Topic.
        actor: The caller.
        db: Database session.
        after: Only Messages with a greater number.
        limit: At most this many, the oldest of them.

    Raises:
        HTTPException: 404 when there is no such Topic for the caller; 403 without an
            Assistant.
    """
    topic = await _topic(db, topic_id, actor)
    messages = list(
        await db.scalars(
            select(Message)
            .where(Message.topic_id == topic.id, Message.number > after)
            .order_by(Message.number)
            .limit(limit)
        )
    )
    return await _detail(request, db, actor, topic, messages)


@router.post("/topics/{topic_id}/messages", status_code=status.HTTP_201_CREATED)
async def post_message(
    request: Request, topic_id: int, body: LegacyMessageIn, actor: ActorDep, db: DB
) -> LegacyMessageOut:
    """Write a Message, in the former shape.

    Args:
        request: The incoming request.
        topic_id: The Topic.
        body: The Message.
        actor: The writer.
        db: Database session.

    Raises:
        HTTPException: 404, 403, 410 as for the paths of decision 0025; 409 ``number_taken``
            or ``turn_limit``; 422 for an unknown addressee, foreign files or a bad
            ``reply_to``.
    """
    topic = await _topic(db, topic_id, actor, lock=True, write=True)
    label = legacy_ref(topic.id)
    if body.number != topic.last_number + 1:
        return await number_taken(request, db, topic, body.number, label, legacy=True)
    if body.reply_to is not None and body.reply_to > topic.last_number:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"There is no Message #{body.reply_to} in {label} to reply to",
        )
    files: list[File] = []
    if body.file_ids:
        files = list(
            await db.scalars(
                select(File).where(
                    File.id.in_(body.file_ids),
                    File.topic_id == topic.id,
                    File.message_id.is_(None),
                )
            )
        )
        if len(files) != len(set(body.file_ids)):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "Attach only files uploaded to this Topic and not attached to another Message",
            )
    message, recipients = await post(
        db, actor, topic, body.body, body.kind, body.to, files, as_human=body.as_human
    )
    message.reply_to = body.reply_to
    await db.commit()
    request.app.state.bus.wake(recipients)
    file_rows = list(await db.scalars(select(File).where(File.message_id == message.id)))
    (out,) = await legacy_messages(db, [message], file_rows, request.app.state.settings)
    return out


@router.post("/topics/{topic_id}/hold")
async def hold_topic(request: Request, topic_id: int, actor: ActorDep, db: DB) -> LegacyTopicOut:
    """Make the calling Assistant the holder, in the former shape.

    Args:
        request: The incoming request.
        topic_id: The Topic.
        actor: The Assistant.
        db: Database session.

    Raises:
        HTTPException: 404, 403, 410 as for the paths of decision 0025.
    """
    if actor.assistant is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only an Assistant holds a Topic")
    topic = await _topic(db, topic_id, actor, lock=True, write=True)
    recipients = await hold(db, actor, topic)
    await db.commit()
    request.app.state.bus.wake(recipients)
    (out,) = await legacy_topics(db, [topic], actor.user.id, request.app.state.settings)
    return out


@router.post("/topics/{topic_id}/stage", status_code=status.HTTP_201_CREATED)
async def post_stage(
    request: Request, topic_id: int, body: LegacyStageIn, actor: ActorDep, db: DB
) -> LegacyMessageOut:
    """Note a stage, in the former shape.

    Args:
        request: The incoming request.
        topic_id: The Topic.
        body: The stage.
        actor: The holding Assistant.
        db: Database session.

    Raises:
        HTTPException: 404, 403, 410 as for the paths of decision 0025; 409 ``not_holder``.
    """
    topic = await _topic(db, topic_id, actor, lock=True, write=True)
    message, recipients = await note_stage(db, actor, topic, body.text, legacy_ref(topic.id))
    await db.commit()
    request.app.state.bus.wake(recipients)
    (out,) = await legacy_messages(db, [message], [], request.app.state.settings)
    return out


@router.patch("/topics/{topic_id}")
async def settle_topic(
    request: Request, topic_id: int, body: TopicPatch, actor: ActorDep, db: DB
) -> LegacyTopicOut:
    """Close or reopen a Topic, in the former shape.

    Args:
        request: The incoming request.
        topic_id: The Topic.
        body: New state and outcome.
        actor: The holding Assistant or a human.
        db: Database session.

    Raises:
        HTTPException: 404, 403, 410 as for the paths of decision 0025; 409 ``not_holder``;
            422 without an outcome.
    """
    topic = await _topic(db, topic_id, actor, lock=True, write=True)
    recipients = await settle(db, actor, topic, body, legacy_ref(topic.id))
    await db.commit()
    request.app.state.bus.wake(recipients)
    (out,) = await legacy_topics(db, [topic], actor.user.id, request.app.state.settings)
    return out


@router.post("/topics/{topic_id}/read")
async def read_up_to(
    request: Request, topic_id: int, body: LegacyReadIn, actor: ActorDep, db: DB
) -> LegacyTopicOut:
    """Record how far the caller has read, in the former shape.

    Args:
        request: The incoming request.
        topic_id: The Topic.
        body: Number of the newest Message read.
        actor: The caller.
        db: Database session.

    Raises:
        HTTPException: 404 when there is no such Topic for the caller.
    """
    topic = await _topic(db, topic_id, actor)
    await mark_read(db, actor, topic, body.number)
    (out,) = await legacy_topics(db, [topic], actor.user.id, request.app.state.settings)
    return out


@router.post("/topics/{topic_id}/files", status_code=status.HTTP_201_CREATED)
async def upload_file(
    request: Request,
    topic_id: int,
    actor: ActorDep,
    db: DB,
    x_file_name: Annotated[str, Header()],
    content_type: Annotated[str, Header()] = "application/octet-stream",
) -> LegacyFileOut:
    """Upload a file into a Topic, in the former shape.

    Args:
        request: The incoming request with the content as its body.
        topic_id: The Topic.
        actor: The caller.
        db: Database session.
        x_file_name: File name, percent-encoded.
        content_type: Media type.

    Raises:
        HTTPException: 404, 403, 410 as for the paths of decision 0025; 422 for an empty name;
            413 over the limit.
        OSError: The file cannot be written.
    """
    topic = await _topic(db, topic_id, actor, write=True)
    file = await store_upload(request, db, actor, topic, x_file_name, content_type)
    (out,) = await legacy_files(db, [file], request.app.state.settings)
    return out


@router.get("/files/{file_id}")
async def download_file(
    request: Request,
    file_id: int,
    actor: ActorDep,
    db: DB,
    download: Annotated[bool, Query()] = False,
) -> FileResponse:
    """Download a file by its database id.

    Args:
        request: The incoming request.
        file_id: The file.
        actor: The caller.
        db: Database session.
        download: Serve an image as an attachment too.

    Raises:
        HTTPException: 404 when there is no such file for the caller.
    """
    file = await db.get(File, file_id)
    if file is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such file")
    await _topic(db, file.topic_id, actor)
    return serve(request, file)
