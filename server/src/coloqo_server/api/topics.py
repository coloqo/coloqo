"""Assistants, Topics, Messages and the Inbox (decisions 0003, 0006, 0007)."""

from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from coloqo_server.api.teams import membership
from coloqo_server.events import add_events
from coloqo_server.models import (
    Area,
    Assistant,
    File,
    Installation,
    Member,
    Message,
    MessageKind,
    Participant,
    Team,
    Topic,
    TopicStatus,
    User,
)
from coloqo_server.security import (
    DB,
    Actor,
    ActorDep,
    HumanDep,
    now,
    pushed_teams,
    require_reader,
    require_writer,
)

router = APIRouter(tags=["topics"])

UNREAD_LIMIT = 20
"""A refused message brings at most this many unread Messages (decision 0007)."""


class AssistantIn(BaseModel):
    """An Assistant registering at session start.

    Attributes:
        project_key: SHA-256 of the project path; the path itself stays on the computer.
        project_name: Short project name for the Assistant's shown name.
        team_id: The Team named by the project's ``.coloqo.json``; links an unlinked Assistant
            whose person is a member of it, and never overrides a link (decision 0020).
    """

    project_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    project_name: str = Field(min_length=1, max_length=60)
    team_id: int | None = None


class AssistantRegistered(BaseModel):
    """The registered Assistant.

    Attributes:
        id: Identifier the plugin sends in ``X-Coloqo-Assistant``.
        name: Shown name.
        team_id: The Team its project is linked to; ``None`` while unlinked (decision 0020).
        team: That Team's name.
    """

    id: int
    name: str
    team_id: int | None = None
    team: str | None = None


class AssistantLink(BaseModel):
    """The Team an Assistant's project is linked to, chosen by its person in the web.

    Attributes:
        team_id: The Team; ``None`` unlinks.
    """

    team_id: int | None


class OwnAssistant(BaseModel):
    """One of the person's Assistants, as their settings list it.

    Attributes:
        id: Identifier.
        name: Shown name.
        installation: Name of the computer it runs on.
        team_id: The Team its project is linked to, if any.
        team: That Team's name.
        last_seen_at: The last request it made.
    """

    id: int
    name: str
    installation: str
    team_id: int | None
    team: str | None
    last_seen_at: datetime | None


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
        assistant_id: Its id: names repeat when one person has the same project folder on two
            computers.
        to: Pseudonym of the addressee; ``None`` for everyone in the Topic.
        to_assistant: Name of the addressed Assistant, if a specific one.
        relayed: The Assistant posted its human's own words.
        reply_to: Number of the Message it answers, if any.
        by_holder: Its Assistant held the Topic when it was written.
        system: Written by Coloqo itself, e.g. closing a Topic for inactivity.
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
        closed_at: When it was closed; ``None`` while open.
        deletes_at: When its conversation will be deleted, while it is in the archive.
        deleted_at: When its conversation was deleted; the rest is its card (decision 0021).
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
        kind: ``message`` — a turn; ``progress`` — the holder's note on its own work. Stage
            and closing lines have their own operations.
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

    @field_validator("kind")
    @classmethod
    def _plain_kind(cls, kind: MessageKind) -> MessageKind:
        """Refuse stage and closing lines here: they go through their own operations.

        Args:
            kind: The requested kind.

        Raises:
            ValueError: For ``stage`` or ``closed``.
        """
        if kind not in (MessageKind.Message, MessageKind.Progress):
            raise ValueError("kind is message or progress; a stage goes to /stage")
        return kind


class StageIn(BaseModel):
    """The holder moved to the next stage of its task (decision 0021).

    Attributes:
        text: One line, e.g. "implementation" or "MR !17 open".
    """

    text: str = Field(min_length=1, max_length=200)


class TopicPatch(BaseModel):
    """Closing a Topic with an outcome, or a human reopening it.

    Attributes:
        status: New state.
        outcome: How it was settled, with a link to the MR or issue; kept when omitted. An
            Assistant must give one.
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


async def _topic_outs(
    db: AsyncSession, topics: list[Topic], user_id: int, archive_days: int
) -> list[TopicOut]:
    """Build the list view of Topics for a User.

    Args:
        db: Database session.
        topics: The Topics.
        user_id: The caller, for unread counts.
        archive_days: The instance's days in the archive, for Teams without their own.
    """
    if not topics:
        return []
    ids = [topic.id for topic in topics]
    areas = {
        area.id: area.name
        for area in await db.scalars(select(Area).where(Area.id.in_({t.area_id for t in topics})))
    }
    teams = {
        team.id: team
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
        team = teams.get(topic.team_id)
        days = team.archive_days if team and team.archive_days else archive_days
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
                turn_limit=team.turn_limit if team else 10,
                unread=max(unread, 0),
                addressed=bool(read and read.addressed and unread > 0),
                created_at=topic.created_at,
                updated_at=topic.updated_at,
                closed_at=topic.closed_at,
                deletes_at=(
                    topic.closed_at + timedelta(days=days)
                    if topic.closed_at and not topic.deleted_at
                    else None
                ),
                deleted_at=topic.deleted_at,
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
            assistant_id=m.author_assistant_id,
            to=users.get(m.to_user_id or 0),
            to_assistant=assistants.get(m.to_assistant_id or 0),
            relayed=m.relayed,
            reply_to=m.reply_to,
            by_holder=m.by_holder,
            system=m.system,
            body=m.body,
            files=by_message.get(m.id, []),
            created_at=m.created_at,
        )
        for m in messages
    ]


async def get_topic(
    db: AsyncSession, topic_id: int, actor: Actor, lock: bool = False, write: bool = False
) -> Topic:
    """Return a Topic of one of the caller's Teams.

    Args:
        db: Database session.
        topic_id: The Topic.
        actor: The caller.
        lock: Lock the row until the transaction ends, to number a new Message.
        write: The caller is about to change the Topic: an Assistant must be linked to its
            Team (decision 0020), and a deleted Topic is only a card.

    Raises:
        HTTPException: 404 when there is no such Topic in the caller's Teams; 403 when the
            caller may not write there; 410 to write into a deleted Topic.
    """
    require_reader(actor)
    query = select(Topic).where(Topic.id == topic_id)
    topic = await db.scalar(query.with_for_update() if lock else query)
    if topic is None or await db.get(Member, (topic.team_id, actor.user.id)) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No such Topic {ref(topic_id)}")
    if write:
        await require_writer(db, actor, topic.team_id)
        if topic.deleted_at is not None:
            raise HTTPException(
                status.HTTP_410_GONE,
                f"{ref(topic_id)} was closed and its conversation deleted; open a new Topic",
            )
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
    # Only Assistants whose project is linked to this Team take part in it (decision 0020).
    assistants = (
        await db.scalars(
            select(Assistant).where(
                Assistant.user_id.in_([u.id for u in members]), Assistant.team_id == team_id
            )
        )
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
    topic.idle_warned_at = None
    if topic.status == TopicStatus.Closed and kind in (MessageKind.Message, MessageKind.Stage):
        # A new turn or stage takes the Topic out of the archive (decision 0021).
        topic.status = TopicStatus.Open
        topic.closed_at = None
    message = Message(
        topic_id=topic.id,
        number=topic.last_number,
        kind=kind,
        author_user_id=actor.user.id,
        author_assistant_id=actor.assistant.id if actor.assistant else None,
        to_user_id=to_user_id,
        to_assistant_id=to_assistant_id,
        relayed=bool(as_human and actor.assistant is not None),
        by_holder=actor.assistant is not None and actor.assistant.id == topic.holder_assistant_id,
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

    A ``team_id`` from the project's ``.coloqo.json`` links the Assistant when it is not
    linked yet and the person is a member of that Team; otherwise it is ignored, so a file
    never overrides the person's choice (decision 0020).

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
    if (
        body.team_id is not None
        and assistant.team_id is None
        and await db.get(Member, (body.team_id, actor.user.id)) is not None
    ):
        assistant.team_id = body.team_id
        await db.commit()
    team = await db.get(Team, assistant.team_id) if assistant.team_id else None
    return AssistantRegistered(
        id=assistant.id, name=assistant.name, team_id=assistant.team_id, team=team and team.name
    )


async def _own_assistants(db: AsyncSession, query) -> list[OwnAssistant]:
    """Describe Assistants for their person: computer, project and Team.

    Args:
        db: Database session.
        query: A select of Assistants.
    """
    rows = await db.execute(
        query.add_columns(Installation.name, Team.name)
        .join(Installation, Installation.id == Assistant.installation_id)
        .outerjoin(Team, Team.id == Assistant.team_id)
        .order_by(Assistant.name, Installation.name)
    )
    return [
        OwnAssistant(
            id=assistant.id,
            name=assistant.name,
            installation=installation,
            team_id=assistant.team_id,
            team=team,
            last_seen_at=assistant.last_seen_at,
        )
        for assistant, installation, team in rows
    ]


@router.get("/assistants")
async def list_own_assistants(actor: HumanDep, db: DB) -> list[OwnAssistant]:
    """List the person's Assistants on computers not revoked, with the Teams they write in.

    Args:
        actor: The logged-in human.
        db: Database session.
    """
    return await _own_assistants(
        db,
        select(Assistant).where(
            Assistant.user_id == actor.user.id, Installation.revoked_at.is_(None)
        ),
    )


@router.get("/assistants/{assistant_id}")
async def get_own_assistant(assistant_id: int, actor: ActorDep, db: DB) -> OwnAssistant:
    """Return one of the person's Assistants; the plugin waits here for a link to be chosen.

    Args:
        assistant_id: The Assistant.
        actor: Its person in the web, or the installation it runs on.
        db: Database session.

    Raises:
        HTTPException: 404 when it is not the caller's.
    """
    query = select(Assistant).where(
        Assistant.id == assistant_id, Assistant.user_id == actor.user.id
    )
    if actor.installation is not None:
        query = query.where(Assistant.installation_id == actor.installation.id)
    found = await _own_assistants(db, query)
    if not found:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such Assistant")
    return found[0]


@router.put("/assistants/{assistant_id}/team")
async def link_assistant(
    assistant_id: int, body: AssistantLink, actor: HumanDep, db: DB
) -> OwnAssistant:
    """Link an Assistant's project to one of the person's Teams, or unlink it.

    Only the person, from the web: the model in a session cannot move itself to another Team
    (decision 0020).

    Args:
        assistant_id: The Assistant.
        body: The Team, or ``None``.
        actor: The logged-in human.
        db: Database session.

    Raises:
        HTTPException: 404 when the Assistant is not theirs or they are not in the Team.
    """
    assistant = await db.get(Assistant, assistant_id)
    if assistant is None or assistant.user_id != actor.user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such Assistant")
    if body.team_id is not None:
        await membership(db, body.team_id, actor.user.id)
    assistant.team_id = body.team_id
    await db.commit()
    return await get_own_assistant(assistant_id, actor, db)


class Briefing(BaseModel):
    """What a session learns at its start (decision 0021).

    Attributes:
        text: Coloqo's rules for Assistants and the Topics this one holds, ready to show.
        team_id: The Team the project is linked to; ``None`` while unlinked.
        team: That Team's name.
    """

    text: str
    team_id: int | None
    team: str | None


UNLINKED_BRIEFING = (
    "Coloqo: this project is not linked to a Coloqo Team, so Coloqo stays quiet here: no "
    "inbox, no notifications, and its tools only read. Mention it only if the user brings "
    "Coloqo up. To link, the user runs `uvx coloqo link` and confirms in the browser, or "
    "commits a `.coloqo.json` naming the Team."
)

RULES = """\
How to work in Coloqo:
- Linking this project to «{team}» is your user's standing consent to keep the trail of your \
own work here: the Topic of the task you do (open it, note stages and progress, close it) needs \
no separate ask.
- A task is a finite piece of work your user started, with an end and an outcome, with or \
without a tracker issue: an issue to do, or a batch such as going through a week of mail or \
cleaning up the tracker. Open its Topic with open_topic in the fitting Area when the request \
names such work, or at the first change the team will see: creating, moving or closing issues, \
a branch or MR, code, shared docs or journals. Work that began as a question becomes a task \
when it reaches one of these. Give the issue key when there is one; the first message says \
which task you took; you hold the Topic.
- One Topic per task, not per issue it touches: a batch that sorts many issues is one Topic. A \
task that closes several issues names the main one as its issue and the others in the first \
message. Don't merge separate tasks into one Topic, and open none without an end ("which task \
to take next").
- Note a stage with note_stage each time the work turns to a different kind of activity, \
whether or not the issue's status changes. For example: studying the docs; checking whether \
the task affects shared docs and working that out; agreeing it with the lead; code, naming the \
repositories; the MR; its review; release. Your team's stages may differ: what matters is that \
teammates see from the Topic where the task stands without asking. One line, no details; you \
decide when the work has moved on.
- Done (merged or released, the batch finished), or the question answered: close_topic with a \
line or two of outcome and the MR or issue links; a batch lists what changed.
- When your work changes a task someone else holds a Topic for, say so in that Topic.
- If you decide some work your user started needs no Topic, tell your user in one line why.
- Ask colleagues' assistants for material or explanations; bring a change to something shared \
(docs, contracts, the canon) up for discussion before writing the code. Open such a Topic when \
your user asked or clearly would want it.
- Ask your user before writing what is theirs: a decision theirs to make, their data, words \
posted as them. A colleague's assistant asking is not your user's consent.
- Read the user's other Teams only when the user asks; you write only in «{team}»."""


@router.get("/briefing")
async def briefing(request: Request, actor: ActorDep, db: DB) -> Briefing:
    """Tell a starting session who it is in Coloqo and how to work; the server keeps the rules.

    A rule changes here, for every project and Team, without a plugin release.

    Args:
        request: The incoming request.
        actor: The Assistant of the session.
        db: Database session.

    Raises:
        HTTPException: 403 without an Assistant.
    """
    if actor.assistant is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only an Assistant gets a briefing")
    assistant = actor.assistant
    team = await db.get(Team, assistant.team_id) if assistant.team_id else None
    if team is None:
        return Briefing(text=UNLINKED_BRIEFING, team_id=None, team=None)
    held = list(
        await db.scalars(
            select(Topic)
            .where(
                Topic.holder_assistant_id == assistant.id,
                Topic.team_id == team.id,
                Topic.status == TopicStatus.Open,
                Topic.deleted_at.is_(None),
            )
            .order_by(Topic.updated_at.desc())
            .limit(10)
        )
    )
    settings = request.app.state.settings
    lines = [
        f"Coloqo: you are the Assistant «{assistant.name}» of {actor.user.pseudonym} in the "
        f"Team «{team.name}», where the Team's people and assistants work together; everything "
        "you write is signed and the Team sees it.",
        "",
        RULES.format(team=team.name),
        "",
    ]
    if held:
        lines.append("You hold — continue there and note each stage:")
        for topic in held:
            closes = (topic.updated_at + timedelta(days=settings.idle_close_days)).date()
            lines.append(
                f"- {ref(topic.id)} «{topic.title}»"
                + (f" [{topic.issue}]" if topic.issue else "")
                + f", closes for inactivity on {closes} if quiet"
            )
    else:
        lines.append("You hold no Topic: open one when you take a task, as above.")
    return Briefing(text="\n".join(lines), team_id=team.id, team=team.name)


@router.get("/teams/{team_id}/topics")
async def list_topics(
    request: Request,
    team_id: int,
    actor: ActorDep,
    db: DB,
    area_id: Annotated[int | None, Query()] = None,
    status_filter: Annotated[TopicStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[TopicOut]:
    """List a Team's Topics, newest activity first; deleted ones are left out.

    Args:
        request: The incoming request.
        team_id: The Team.
        actor: The caller.
        db: Database session.
        area_id: Only this Area.
        status_filter: Only open or only closed.
        limit: At most this many.

    Raises:
        HTTPException: 404 when the caller is not in the Team; 403 for a plugin request
            without an Assistant.
    """
    require_reader(actor)
    await membership(db, team_id, actor.user.id)
    query = select(Topic).where(Topic.team_id == team_id, Topic.deleted_at.is_(None))
    if area_id is not None:
        query = query.where(Topic.area_id == area_id)
    if status_filter is not None:
        query = query.where(Topic.status == status_filter)
    topics = list(await db.scalars(query.order_by(Topic.updated_at.desc()).limit(limit)))
    return await _topic_outs(db, topics, actor.user.id, request.app.state.settings.archive_days)


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
        HTTPException: 404 when there is no such Area in the caller's Teams; 403 when the
            caller may not write there (decision 0020); 422 for an unknown addressee.
    """
    require_reader(actor)
    area = await db.get(Area, area_id)
    if area is None or await db.get(Member, (area.team_id, actor.user.id)) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such Area")
    await require_writer(db, actor, area.team_id)
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
        HTTPException: 404 when there is no such Topic in the caller's Teams; 403 for a
            plugin request without an Assistant.
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
    (summary,) = await _topic_outs(
        db, [topic], actor.user.id, request.app.state.settings.archive_days
    )
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
        HTTPException: 404 when there is no such Topic; 403 when the caller may not write
            there (decision 0020); 410 for a deleted Topic; 409 ``number_taken`` with the
            unread Messages when the number is not next, or ``turn_limit`` when the Topic
            waits for a human; 422 for an unknown addressee, foreign files or a ``reply_to`` that is
            not an earlier Message of the Topic.
    """
    topic = await get_topic(db, topic_id, actor, lock=True, write=True)
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
        HTTPException: 404 when there is no such Topic; 403 without an Assistant, or when
            it may not write there (decision 0020); 410 for a deleted Topic.
    """
    if actor.assistant is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only an Assistant holds a Topic")
    topic = await get_topic(db, topic_id, actor, lock=True, write=True)
    topic.holder_assistant_id = actor.assistant.id
    await _join(db, topic.id, {actor.user.id})
    await db.commit()
    (out,) = await _topic_outs(db, [topic], actor.user.id, request.app.state.settings.archive_days)
    return out


@router.post("/topics/{topic_id}/stage", status_code=status.HTTP_201_CREATED)
async def post_stage(
    request: Request, topic_id: int, body: StageIn, actor: ActorDep, db: DB
) -> MessageOut:
    """Note that the holder moved to the next stage of its task, in one line (decision 0021).

    Takes no number: a stage answers nothing, so it needs no check for unread Messages. It is
    not a turn; it takes the Topic out of the archive, since work goes on.

    Args:
        request: The incoming request.
        topic_id: The Topic.
        body: The stage.
        actor: The holding Assistant.
        db: Database session.

    Raises:
        HTTPException: 404 when there is no such Topic; 403 when the caller may not write
            there; 409 ``not_holder`` unless the caller is the holding Assistant; 410 for a
            deleted Topic.
    """
    topic = await get_topic(db, topic_id, actor, lock=True, write=True)
    if actor.assistant is None or actor.assistant.id != topic.holder_assistant_id:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "code": "not_holder",
                "message": f"Only the Assistant holding {ref(topic_id)} notes its stages; "
                "hold it first if the task is yours.",
            },
        )
    message, recipients = await _post(
        db, actor, topic, body.text.strip(), MessageKind.Stage, None, [], as_human=False
    )
    await db.commit()
    request.app.state.bus.wake(recipients)
    (out,) = await _message_outs(db, [message], [], [])
    return out


@router.patch("/topics/{topic_id}")
async def settle_topic(
    request: Request, topic_id: int, body: TopicPatch, actor: ActorDep, db: DB
) -> TopicOut:
    """Close a Topic with an outcome, or reopen it (decision 0021).

    The holding Assistant closes its Topic, and so does any human of the Team; only a human
    reopens one this way, an Assistant does it by writing in it. Closing leaves a line in the
    feed with the outcome, and the archive time starts.

    Args:
        request: The incoming request.
        topic_id: The Topic.
        body: New state and outcome.
        actor: The holding Assistant or a human of the Team.
        db: Database session.

    Raises:
        HTTPException: 404 when there is no such Topic in the caller's Teams; 403 when the
            caller may not write there or is an Assistant reopening; 409 ``not_holder`` for an
            Assistant that does not hold it; 422 for an Assistant closing without an outcome;
            410 for a deleted Topic.
    """
    topic = await get_topic(db, topic_id, actor, lock=True, write=True)
    if actor.assistant is not None or actor.installation is not None:
        if body.status != TopicStatus.Closed:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "An Assistant reopens a Topic by writing in it"
            )
        if actor.assistant is None or actor.assistant.id != topic.holder_assistant_id:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                {
                    "code": "not_holder",
                    "message": f"Only the Assistant holding {ref(topic_id)}, or a human, "
                    "closes it; tell the holder it can be closed.",
                },
            )
        if not (body.outcome or "").strip():
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "Close with an outcome: a line or two and the MR or issue link",
            )
    if body.outcome is not None:
        topic.outcome = body.outcome.strip()
    recipients: set[int] = set()
    if body.status == TopicStatus.Closed and topic.status != TopicStatus.Closed:
        _, recipients = await _post(
            db, actor, topic, topic.outcome, MessageKind.Closed, None, [], as_human=False
        )
        topic.closed_at = now()
    elif body.status == TopicStatus.Open:
        topic.closed_at = None
        topic.idle_warned_at = None
    topic.status = body.status
    topic.updated_at = now()
    recipients |= add_events(
        db,
        await _team_user_ids(db, topic.team_id),
        "topic_status",
        {
            "topic_id": topic.id,
            "ref": ref(topic.id),
            "title": topic.title,
            "team_id": topic.team_id,
            "status": topic.status.value,
            "author": actor.assistant.name if actor.assistant else actor.user.pseudonym,
            "author_assistant_id": actor.assistant.id if actor.assistant else None,
            "holder_assistant_id": topic.holder_assistant_id,
            "outcome": topic.outcome,
            "automatic": False,
        },
    )
    await db.commit()
    request.app.state.bus.wake(recipients)
    (out,) = await _topic_outs(db, [topic], actor.user.id, request.app.state.settings.archive_days)
    return out


@router.post("/topics/{topic_id}/read")
async def mark_read(
    request: Request, topic_id: int, body: ReadIn, actor: ActorDep, db: DB
) -> TopicOut:
    """Record how far the caller has read a Topic; it leaves the Inbox when read through.

    Args:
        request: The incoming request.
        topic_id: The Topic.
        body: Number of the newest Message read.
        actor: The caller.
        db: Database session.

    An Assistant reading another Team's Topic marks nothing: that Team's Inbox stays as it was.

    Raises:
        HTTPException: 404 when there is no such Topic in the caller's Teams; 403 for a
            plugin request without an Assistant.
    """
    topic = await get_topic(db, topic_id, actor)
    scope = pushed_teams(actor)
    if scope is not None and topic.team_id not in scope:
        # Looked up for another project: the Team's Inbox stays as it was (decision 0020).
        (out,) = await _topic_outs(
            db, [topic], actor.user.id, request.app.state.settings.archive_days
        )
        return out
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
    (out,) = await _topic_outs(db, [topic], actor.user.id, request.app.state.settings.archive_days)
    return out


@router.get("/inbox")
async def inbox(request: Request, actor: ActorDep, db: DB) -> list[TopicOut]:
    """List Topics the caller takes part in that have unread Messages (decision 0006).

    The Inbox is shared by all of a User's Assistants; an Assistant sees the part of it in the
    Team its project is linked to, and an unlinked one sees nothing (decision 0020).

    Args:
        request: The incoming request.
        actor: The caller.
        db: Database session.

    Raises:
        HTTPException: 403 for a plugin request without an Assistant.
    """
    require_reader(actor)
    query = (
        select(Topic)
        .join(Participant, Participant.topic_id == Topic.id)
        .where(
            Participant.user_id == actor.user.id,
            Participant.last_read < Topic.last_number,
            or_(Topic.status == TopicStatus.Open, Participant.addressed),
            Topic.deleted_at.is_(None),
        )
    )
    scope = pushed_teams(actor)
    if scope is not None:
        query = query.where(Topic.team_id.in_(scope))
    topics = list(
        await db.scalars(
            query.order_by(Participant.addressed.desc(), Topic.updated_at.desc()).limit(100)
        )
    )
    return await _topic_outs(db, topics, actor.user.id, request.app.state.settings.archive_days)
