"""Assistants, Topics, Messages and the Inbox (decisions 0003, 0006, 0007)."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from coloqo_server.api.teams import membership
from coloqo_server.events import add_events
from coloqo_server.models import (
    Area,
    Assistant,
    File,
    Member,
    Message,
    MessageKind,
    Participant,
    Team,
    Topic,
    TopicStatus,
    User,
)
from coloqo_server.security import DB, Actor, ActorDep, HumanDep, now

router = APIRouter(tags=["topics"])

UNREAD_LIMIT = 20
"""A refused message brings at most this many unread Messages (decision 0007)."""


class AssistantIn(BaseModel):
    """An Assistant registering at session start.

    Attributes:
        project_key: SHA-256 of the project path; the path itself stays on the computer.
        project_name: Short project name for the Assistant's shown name.
    """

    project_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    project_name: str = Field(min_length=1, max_length=60)


class AssistantRegistered(BaseModel):
    """The registered Assistant.

    Attributes:
        id: Identifier the plugin sends in ``X-Coloqo-Assistant``.
        name: Shown name.
    """

    id: int
    name: str


class FileOut(BaseModel):
    """A file shared in a Topic.

    Attributes:
        id: Identifier.
        name: File name.
        size: Size in bytes.
        sha256: Checksum.
        content_type: Media type given by the uploader.
        preview: The web shows it inline: a raster image recognised by its content, no larger
            than the instance allows (decision 0018).
        uploaded_by: Pseudonym of the uploader.
        message_number: The Message it is attached to, if any.
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


class MessageOut(BaseModel):
    """A Message in a Topic.

    Attributes:
        number: Position in the Topic.
        kind: A turn or a progress note.
        author: Pseudonym of the User on whose behalf it is written.
        assistant: Name of the Assistant that wrote it; ``None`` when the human wrote it.
        to: Pseudonym of the addressee; ``None`` for everyone in the Topic.
        to_assistant: Name of the addressed Assistant, if a specific one.
        relayed: The Assistant posted its human's own words.
        reply_to: Number of the Message it answers, if any.
        body: Markdown text.
        files: Files attached to it.
        created_at: When it was written.
    """

    number: int
    kind: MessageKind
    author: str | None
    assistant: str | None
    to: str | None
    to_assistant: str | None
    relayed: bool
    reply_to: int | None
    body: str
    files: list[FileOut]
    created_at: datetime


class TopicOut(BaseModel):
    """A Topic in a list.

    Attributes:
        id: Identifier.
        ref: Short reference, ``T-<id>``.
        team_id: The Team.
        area_id: The Area.
        area: Name of the Area.
        title: The question.
        issue: Tracker issue key or link.
        status: Open or closed.
        outcome: How a human settled it.
        holder: Name of the holding Assistant.
        holder_assistant_id: Its id.
        created_by: Pseudonym of whoever opened it.
        last_number: Number of the newest Message.
        turns_since_human: Assistants' turns since the last human Message.
        turn_limit: The Team's limit of such turns.
        unread: Messages the caller has not read, if they take part.
        addressed: Some unread Message is addressed to the caller.
        created_at: Creation time.
        updated_at: Time of the newest Message.
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


class TopicDetail(TopicOut):
    """A Topic with its Messages.

    Attributes:
        messages: Messages after the requested number, oldest first.
        files: All files shared in the Topic.
    """

    messages: list[MessageOut]
    files: list[FileOut]


class TopicIn(BaseModel):
    """A new Topic with its first Message.

    Attributes:
        title: The question, one line.
        body: The first Message: what is asked or which task was started.
        issue: Tracker issue key or link, if the Topic is for one.
        to: Pseudonym of a Member or an Assistant's name, if the first Message is for them.
    """

    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=50_000)
    issue: str = Field(default="", max_length=300)
    to: str | None = None


class MessageIn(BaseModel):
    """A new Message.

    Attributes:
        number: The number the writer believes is next: the Topic's ``last_number + 1``.
        body: Markdown text.
        kind: ``message`` — a turn; ``progress`` — the holder's note on its own work.
        to: Pseudonym of a Member or an Assistant's name; empty for everyone in the Topic.
        file_ids: Files uploaded to this Topic to attach.
        as_human: The Assistant relays its human's own words; resets the turn count.
        reply_to: Number of an earlier Message of the Topic this one answers.
    """

    number: int = Field(ge=1)
    body: str = Field(min_length=1, max_length=50_000)
    kind: MessageKind = MessageKind.Message
    to: str | None = None
    file_ids: list[int] = Field(default_factory=list, max_length=20)
    as_human: bool = False
    reply_to: int | None = Field(default=None, ge=1)


class TopicPatch(BaseModel):
    """A human settling or reopening a Topic.

    Attributes:
        status: New state.
        outcome: How it was settled, with a link to the MR or issue; kept when omitted.
    """

    status: TopicStatus
    outcome: str | None = Field(default=None, max_length=5000)


class ReadIn(BaseModel):
    """How far the caller has read a Topic.

    Attributes:
        number: Number of the newest Message read.
    """

    number: int = Field(ge=0)


def ref(topic_id: int) -> str:
    """Return the short reference of a Topic.

    Args:
        topic_id: The Topic.
    """
    return f"T-{topic_id}"


async def _names(
    db: AsyncSession, user_ids: set[int | None], assistant_ids: set[int | None]
) -> tuple[dict[int, str | None], dict[int, str]]:
    """Return pseudonyms and Assistant names by id.

    Args:
        db: Database session.
        user_ids: Users to name.
        assistant_ids: Assistants to name.
    """
    users = {
        row.id: row.pseudonym
        for row in await db.scalars(select(User).where(User.id.in_(user_ids - {None})))
    }
    assistants = {
        row.id: row.name
        for row in await db.scalars(
            select(Assistant).where(Assistant.id.in_(assistant_ids - {None}))
        )
    }
    return users, assistants


async def _topic_outs(db: AsyncSession, topics: list[Topic], user_id: int) -> list[TopicOut]:
    """Build the list view of Topics for a User.

    Args:
        db: Database session.
        topics: The Topics.
        user_id: The caller, for unread counts.
    """
    if not topics:
        return []
    ids = [topic.id for topic in topics]
    areas = {
        area.id: area.name
        for area in await db.scalars(select(Area).where(Area.id.in_({t.area_id for t in topics})))
    }
    limits = {
        team.id: team.turn_limit
        for team in await db.scalars(select(Team).where(Team.id.in_({t.team_id for t in topics})))
    }
    reads = {
        p.topic_id: p
        for p in await db.scalars(
            select(Participant).where(Participant.topic_id.in_(ids), Participant.user_id == user_id)
        )
    }
    users, assistants = await _names(
        db, {t.created_by for t in topics}, {t.holder_assistant_id for t in topics}
    )
    result = []
    for topic in topics:
        read = reads.get(topic.id)
        unread = topic.last_number - read.last_read if read else 0
        result.append(
            TopicOut(
                id=topic.id,
                ref=ref(topic.id),
                team_id=topic.team_id,
                area_id=topic.area_id,
                area=areas.get(topic.area_id, ""),
                title=topic.title,
                issue=topic.issue,
                status=topic.status,
                outcome=topic.outcome,
                holder=assistants.get(topic.holder_assistant_id or 0),
                holder_assistant_id=topic.holder_assistant_id,
                created_by=users.get(topic.created_by),
                last_number=topic.last_number,
                turns_since_human=topic.turns_since_human,
                turn_limit=limits.get(topic.team_id, 10),
                unread=max(unread, 0),
                addressed=bool(read and read.addressed and unread > 0),
                created_at=topic.created_at,
                updated_at=topic.updated_at,
            )
        )
    return result


async def _file_outs(db: AsyncSession, files: list[File], preview_max_bytes: int) -> list[FileOut]:
    """Build the view of files.

    Args:
        db: Database session.
        files: The files.
        preview_max_bytes: Largest image shown inline.
    """
    users, _ = await _names(db, {f.uploaded_by for f in files}, set())
    numbers = {
        message.id: message.number
        for message in await db.scalars(
            select(Message).where(Message.id.in_({f.message_id for f in files} - {None}))
        )
    }
    return [
        FileOut(
            id=f.id,
            name=f.name,
            size=f.size,
            sha256=f.sha256,
            content_type=f.content_type,
            preview=f.image_type is not None and f.size <= preview_max_bytes,
            uploaded_by=users.get(f.uploaded_by),
            message_number=numbers.get(f.message_id or 0),
            created_at=f.created_at,
        )
        for f in files
    ]


async def _message_outs(
    db: AsyncSession, messages: list[Message], files: list[FileOut], file_rows: list[File]
) -> list[MessageOut]:
    """Build the view of Messages with their attached files.

    Args:
        db: Database session.
        messages: The Messages.
        files: Views of the Topic's files.
        file_rows: The same files as rows, to match them to Messages.
    """
    users, assistants = await _names(
        db,
        {m.author_user_id for m in messages} | {m.to_user_id for m in messages},
        {m.author_assistant_id for m in messages} | {m.to_assistant_id for m in messages},
    )
    by_message: dict[int, list[FileOut]] = {}
    for row, view in zip(file_rows, files, strict=True):
        if row.message_id is not None:
            by_message.setdefault(row.message_id, []).append(view)
    return [
        MessageOut(
            number=m.number,
            kind=m.kind,
            author=users.get(m.author_user_id),
            assistant=assistants.get(m.author_assistant_id or 0),
            to=users.get(m.to_user_id or 0),
            to_assistant=assistants.get(m.to_assistant_id or 0),
            relayed=m.relayed,
            reply_to=m.reply_to,
            body=m.body,
            files=by_message.get(m.id, []),
            created_at=m.created_at,
        )
        for m in messages
    ]


async def get_topic(db: AsyncSession, topic_id: int, actor: Actor, lock: bool = False) -> Topic:
    """Return a Topic of one of the caller's Teams.

    Args:
        db: Database session.
        topic_id: The Topic.
        actor: The caller.
        lock: Lock the row until the transaction ends, to number a new Message.

    Raises:
        HTTPException: 404 when there is no such Topic in the caller's Teams.
    """
    query = select(Topic).where(Topic.id == topic_id)
    topic = await db.scalar(query.with_for_update() if lock else query)
    if topic is None or await db.get(Member, (topic.team_id, actor.user.id)) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No such Topic {ref(topic_id)}")
    return topic


async def _addressee(
    db: AsyncSession, team_id: int, to: str | None
) -> tuple[int | None, int | None]:
    """Resolve whom a Message is addressed to in a Team.

    Args:
        db: Database session.
        team_id: The Team.
        to: A Member's pseudonym or an Assistant's name, any case; empty for everyone.

    Raises:
        HTTPException: 422 when nobody in the Team has this name; the detail lists the
            names that would work.
    """
    if not to or not to.strip():
        return None, None
    name = to.strip().lstrip("@").lower()
    members = (
        (
            await db.execute(
                select(User)
                .join(Member, Member.user_id == User.id)
                .where(Member.team_id == team_id)
            )
        )
        .scalars()
        .all()
    )
    for user in members:
        if user.pseudonym and user.pseudonym.lower() == name:
            return user.id, None
    assistants = (
        await db.scalars(select(Assistant).where(Assistant.user_id.in_([u.id for u in members])))
    ).all()
    for assistant in assistants:
        if assistant.name.lower() == name:
            return assistant.user_id, assistant.id
    known = sorted([u.pseudonym for u in members if u.pseudonym] + [a.name for a in assistants])
    raise HTTPException(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        f"Nobody in the Team is called {to!r}. Members and Assistants: {', '.join(known)}",
    )


async def _join(db: AsyncSession, topic_id: int, user_ids: set[int | None]) -> None:
    """Make Users participants of a Topic if they are not yet.

    Args:
        db: Database session.
        topic_id: The Topic.
        user_ids: The Users.
    """
    for user_id in user_ids - {None}:
        await db.execute(
            insert(Participant)
            .values(topic_id=topic_id, user_id=user_id, last_read=0, addressed=False)
            .on_conflict_do_nothing()
        )


async def _team_user_ids(db: AsyncSession, team_id: int) -> list[int]:
    """Return the ids of a Team's Members.

    Args:
        db: Database session.
        team_id: The Team.
    """
    return list(await db.scalars(select(Member.user_id).where(Member.team_id == team_id)))


async def _post(
    db: AsyncSession,
    actor: Actor,
    topic: Topic,
    body: str,
    kind: MessageKind,
    to: str | None,
    file_ids: list[int],
    as_human: bool,
    counts_as_turn: bool = True,
) -> tuple[Message, set[int]]:
    """Write the next Message into a locked Topic and queue its events.

    Args:
        db: Database session, with the Topic row locked.
        actor: The writer.
        topic: The Topic.
        body: Text.
        kind: Turn or progress note.
        to: Addressee name, if any.
        file_ids: Files of the Topic to attach.
        as_human: The Assistant relays its human's words.
        counts_as_turn: An Assistant's Message counts against the turn limit; the opening
            Message of a Topic does not.

    Raises:
        HTTPException: 422 for an unknown addressee or files not in this Topic; 409 when the
            Topic waits for a human (decision 0007).
    """
    to_user_id, to_assistant_id = await _addressee(db, topic.team_id, to)
    human = actor.is_human or as_human
    team = await db.get(Team, topic.team_id)
    assert team is not None
    if human:
        topic.turns_since_human = 0
    elif kind == MessageKind.Message and counts_as_turn:
        if topic.turns_since_human >= team.turn_limit:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                {
                    "code": "turn_limit",
                    "message": (
                        f"{ref(topic.id)} has reached {team.turn_limit} Assistants' turns without "
                        "a human, and waits for one. Ask your human: they can write in the Topic "
                        "in the web interface, or tell you what to post, and you post their words "
                        "with as_human=true."
                    ),
                },
            )
        topic.turns_since_human += 1
    files = []
    if file_ids:
        files = list(
            await db.scalars(
                select(File).where(
                    File.id.in_(file_ids), File.topic_id == topic.id, File.message_id.is_(None)
                )
            )
        )
        if len(files) != len(set(file_ids)):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "Attach only files uploaded to this Topic and not attached to another Message",
            )
    topic.last_number += 1
    topic.updated_at = now()
    if topic.status == TopicStatus.Closed and kind == MessageKind.Message:
        topic.status = TopicStatus.Open
    message = Message(
        topic_id=topic.id,
        number=topic.last_number,
        kind=kind,
        author_user_id=actor.user.id,
        author_assistant_id=actor.assistant.id if actor.assistant else None,
        to_user_id=to_user_id,
        to_assistant_id=to_assistant_id,
        relayed=bool(as_human and actor.assistant is not None),
        body=body,
    )
    db.add(message)
    await db.flush()
    for file in files:
        file.message_id = message.id
    await _join(db, topic.id, {actor.user.id, to_user_id})
    await db.execute(
        update(Participant)
        .where(Participant.topic_id == topic.id, Participant.user_id == actor.user.id)
        .values(last_read=topic.last_number)
    )
    if to_user_id is not None and to_user_id != actor.user.id:
        await db.execute(
            update(Participant)
            .where(Participant.topic_id == topic.id, Participant.user_id == to_user_id)
            .values(addressed=True)
        )
    posters = set(
        await db.scalars(
            select(Message.author_assistant_id)
            .where(Message.topic_id == topic.id, Message.author_assistant_id.is_not(None))
            .distinct()
        )
    )
    area = await db.get(Area, topic.area_id)
    recipients = add_events(
        db,
        await _team_user_ids(db, topic.team_id),
        "message",
        {
            "topic_id": topic.id,
            "ref": ref(topic.id),
            "title": topic.title,
            "team_id": topic.team_id,
            "area": area.name if area else "",
            "number": message.number,
            "kind": kind.value,
            "author": actor.user.pseudonym,
            "author_user_id": actor.user.id,
            "author_assistant_id": message.author_assistant_id,
            "assistant": actor.assistant.name if actor.assistant else None,
            "human": human,
            "to_user_id": to_user_id,
            "to_assistant_id": to_assistant_id,
            "holder_assistant_id": topic.holder_assistant_id,
            "assistant_ids": sorted(posters | {topic.holder_assistant_id} - {None}),
        },
    )
    return message, recipients


@router.post("/assistants")
async def register_assistant(body: AssistantIn, actor: ActorDep, db: DB) -> AssistantRegistered:
    """Register the calling installation's Assistant for a project (decision 0003).

    One Assistant per installation and project: the plugin's tools and its watch in that
    project act as it.

    Args:
        body: The project.
        actor: The plugin.
        db: Database session.

    Raises:
        HTTPException: 403 for a web session: only the plugin registers Assistants.
    """
    if actor.installation is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the plugin registers Assistants")
    name = f"{actor.user.pseudonym} · {body.project_name.strip()}"
    await db.execute(
        insert(Assistant)
        .values(
            user_id=actor.user.id,
            installation_id=actor.installation.id,
            project_key=body.project_key,
            name=name,
            last_seen_at=now(),
        )
        .on_conflict_do_update(
            index_elements=["installation_id", "project_key"],
            set_={"name": name, "last_seen_at": now()},
        )
    )
    await db.commit()
    assistant = await db.scalar(
        select(Assistant).where(
            Assistant.installation_id == actor.installation.id,
            Assistant.project_key == body.project_key,
        )
    )
    assert assistant is not None
    return AssistantRegistered(id=assistant.id, name=assistant.name)


@router.get("/teams/{team_id}/topics")
async def list_topics(
    team_id: int,
    actor: ActorDep,
    db: DB,
    area_id: Annotated[int | None, Query()] = None,
    status_filter: Annotated[TopicStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[TopicOut]:
    """List a Team's Topics, newest activity first.

    Args:
        team_id: The Team.
        actor: The caller.
        db: Database session.
        area_id: Only this Area.
        status_filter: Only open or only closed.
        limit: At most this many.

    Raises:
        HTTPException: 404 when the caller is not in the Team.
    """
    await membership(db, team_id, actor.user.id)
    query = select(Topic).where(Topic.team_id == team_id)
    if area_id is not None:
        query = query.where(Topic.area_id == area_id)
    if status_filter is not None:
        query = query.where(Topic.status == status_filter)
    topics = list(await db.scalars(query.order_by(Topic.updated_at.desc()).limit(limit)))
    return await _topic_outs(db, topics, actor.user.id)


@router.post("/areas/{area_id}/topics", status_code=status.HTTP_201_CREATED)
async def create_topic(
    request: Request, area_id: int, body: TopicIn, actor: ActorDep, db: DB
) -> TopicDetail:
    """Open a Topic in an Area with its first Message; the calling Assistant holds it.

    Args:
        request: The incoming request.
        area_id: The Area.
        body: Title and first Message.
        actor: The caller.
        db: Database session.

    Raises:
        HTTPException: 404 when there is no such Area in the caller's Teams; 422 for an
            unknown addressee.
    """
    area = await db.get(Area, area_id)
    if area is None or await db.get(Member, (area.team_id, actor.user.id)) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such Area")
    topic = Topic(
        team_id=area.team_id,
        area_id=area.id,
        title=body.title.strip(),
        issue=body.issue.strip(),
        status=TopicStatus.Open,
        outcome="",
        created_by=actor.user.id,
        holder_assistant_id=actor.assistant.id if actor.assistant else None,
        last_number=0,
        turns_since_human=0,
    )
    to_user_id, to_assistant_id = await _addressee(db, area.team_id, body.to)
    db.add(topic)
    await db.flush()
    recipients = add_events(
        db,
        await _team_user_ids(db, topic.team_id),
        "topic",
        {
            "topic_id": topic.id,
            "ref": ref(topic.id),
            "title": topic.title,
            "team_id": topic.team_id,
            "area": area.name,
            "author": actor.user.pseudonym,
            "author_user_id": actor.user.id,
            "author_assistant_id": topic.holder_assistant_id,
            "holder_assistant_id": topic.holder_assistant_id,
            "to_user_id": to_user_id,
            "to_assistant_id": to_assistant_id,
        },
    )
    # The opening Message is not a turn: the conversation starts with it.
    _, more = await _post(
        db,
        actor,
        topic,
        body.body,
        MessageKind.Message,
        body.to,
        [],
        as_human=False,
        counts_as_turn=False,
    )
    await db.commit()
    request.app.state.bus.wake(recipients | more)
    return await read_topic(request, topic.id, actor, db)


@router.get("/topics/{topic_id}")
async def read_topic(
    request: Request,
    topic_id: int,
    actor: ActorDep,
    db: DB,
    after: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> TopicDetail:
    """Return a Topic with its Messages after a number.

    Args:
        request: The incoming request.
        topic_id: The Topic.
        actor: The caller.
        db: Database session.
        after: Only Messages with a greater number.
        limit: At most this many Messages, the oldest of them.

    Raises:
        HTTPException: 404 when there is no such Topic in the caller's Teams.
    """
    topic = await get_topic(db, topic_id, actor)
    messages = list(
        await db.scalars(
            select(Message)
            .where(Message.topic_id == topic.id, Message.number > after)
            .order_by(Message.number)
            .limit(limit)
        )
    )
    file_rows = list(
        await db.scalars(select(File).where(File.topic_id == topic.id).order_by(File.id))
    )
    files = await _file_outs(db, file_rows, request.app.state.settings.preview_max_bytes)
    (summary,) = await _topic_outs(db, [topic], actor.user.id)
    return TopicDetail(
        **summary.model_dump(),
        messages=await _message_outs(db, messages, files, file_rows),
        files=files,
    )


@router.post("/topics/{topic_id}/messages", status_code=status.HTTP_201_CREATED)
async def post_message(
    request: Request, topic_id: int, body: MessageIn, actor: ActorDep, db: DB
) -> MessageOut:
    """Write a Message with the number the writer believes is next (decision 0007).

    Args:
        request: The incoming request.
        topic_id: The Topic.
        body: The Message.
        actor: The writer.
        db: Database session.

    Raises:
        HTTPException: 404 when there is no such Topic; 409 ``number_taken`` with the unread
            Messages when the number is not next, or ``turn_limit`` when the Topic waits for
            a human; 422 for an unknown addressee, foreign files or a ``reply_to`` that is
            not an earlier Message of the Topic.
    """
    topic = await get_topic(db, topic_id, actor, lock=True)
    if body.number != topic.last_number + 1:
        unread_rows = list(
            await db.scalars(
                select(Message)
                .where(Message.topic_id == topic.id, Message.number >= body.number)
                .order_by(Message.number)
                .limit(UNREAD_LIMIT + 1)
            )
        )
        file_rows = list(await db.scalars(select(File).where(File.topic_id == topic_id)))
        files = await _file_outs(db, file_rows, request.app.state.settings.preview_max_bytes)
        unread = await _message_outs(db, unread_rows[:UNREAD_LIMIT], files, file_rows)
        too_many = len(unread_rows) > UNREAD_LIMIT
        next_number = topic.last_number + 1
        await db.rollback()
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "detail": {
                    "code": "number_taken",
                    "message": (
                        f"Message {body.number} is not next in {ref(topic_id)}: the next number is "
                        f"{next_number}. "
                        + (
                            "There are many unread Messages: reread the Topic."
                            if too_many
                            else "Read the Messages below, then send again with the next number."
                        )
                    ),
                    "next_number": next_number,
                    "unread": [m.model_dump(mode="json") for m in unread],
                    "reread": too_many,
                }
            },
        )
    if body.reply_to is not None and body.reply_to > topic.last_number:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"There is no Message #{body.reply_to} in {ref(topic_id)} to reply to",
        )
    message, recipients = await _post(
        db, actor, topic, body.body, body.kind, body.to, body.file_ids, body.as_human
    )
    message.reply_to = body.reply_to
    await db.commit()
    request.app.state.bus.wake(recipients)
    file_rows = list(await db.scalars(select(File).where(File.message_id == message.id)))
    files = await _file_outs(db, file_rows, request.app.state.settings.preview_max_bytes)
    (out,) = await _message_outs(db, [message], files, file_rows)
    return out


@router.post("/topics/{topic_id}/hold")
async def hold_topic(request: Request, topic_id: int, actor: ActorDep, db: DB) -> TopicOut:
    """Make the calling Assistant the Topic's holder (decision 0006).

    Args:
        request: The incoming request.
        topic_id: The Topic.
        actor: The Assistant.
        db: Database session.

    Raises:
        HTTPException: 404 when there is no such Topic; 403 without an Assistant.
    """
    if actor.assistant is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only an Assistant holds a Topic")
    topic = await get_topic(db, topic_id, actor, lock=True)
    topic.holder_assistant_id = actor.assistant.id
    await _join(db, topic.id, {actor.user.id})
    await db.commit()
    (out,) = await _topic_outs(db, [topic], actor.user.id)
    return out


@router.patch("/topics/{topic_id}")
async def settle_topic(
    request: Request, topic_id: int, body: TopicPatch, actor: HumanDep, db: DB
) -> TopicOut:
    """Close a Topic with an outcome, or reopen it; a human's decision (decision 0003).

    Args:
        request: The incoming request.
        topic_id: The Topic.
        body: New state and outcome.
        actor: The logged-in human.
        db: Database session.

    Raises:
        HTTPException: 404 when there is no such Topic in the caller's Teams.
    """
    topic = await get_topic(db, topic_id, actor, lock=True)
    topic.status = body.status
    if body.outcome is not None:
        topic.outcome = body.outcome.strip()
    topic.updated_at = now()
    recipients = add_events(
        db,
        await _team_user_ids(db, topic.team_id),
        "topic_status",
        {
            "topic_id": topic.id,
            "ref": ref(topic.id),
            "title": topic.title,
            "team_id": topic.team_id,
            "status": topic.status.value,
            "author": actor.user.pseudonym,
            "holder_assistant_id": topic.holder_assistant_id,
        },
    )
    await db.commit()
    request.app.state.bus.wake(recipients)
    (out,) = await _topic_outs(db, [topic], actor.user.id)
    return out


@router.post("/topics/{topic_id}/read")
async def mark_read(topic_id: int, body: ReadIn, actor: ActorDep, db: DB) -> TopicOut:
    """Record how far the caller has read a Topic; it leaves the Inbox when read through.

    Args:
        topic_id: The Topic.
        body: Number of the newest Message read.
        actor: The caller.
        db: Database session.

    Raises:
        HTTPException: 404 when there is no such Topic in the caller's Teams.
    """
    topic = await get_topic(db, topic_id, actor)
    number = min(body.number, topic.last_number)
    await db.execute(
        insert(Participant)
        .values(topic_id=topic.id, user_id=actor.user.id, last_read=number, addressed=False)
        .on_conflict_do_update(
            index_elements=["topic_id", "user_id"],
            set_={
                "last_read": func.greatest(Participant.last_read, number),
                "addressed": Participant.addressed & (number < topic.last_number),
            },
        )
    )
    await db.commit()
    (out,) = await _topic_outs(db, [topic], actor.user.id)
    return out


@router.get("/inbox")
async def inbox(actor: ActorDep, db: DB) -> list[TopicOut]:
    """List Topics the caller takes part in that have unread Messages (decision 0006).

    The Inbox is shared by all of a User's Assistants.

    Args:
        actor: The caller.
        db: Database session.
    """
    topics = list(
        await db.scalars(
            select(Topic)
            .join(Participant, Participant.topic_id == Topic.id)
            .where(
                Participant.user_id == actor.user.id,
                Participant.last_read < Topic.last_number,
                or_(Topic.status == TopicStatus.Open, Participant.addressed),
            )
            .order_by(Participant.addressed.desc(), Topic.updated_at.desc())
            .limit(100)
        )
    )
    return await _topic_outs(db, topics, actor.user.id)
