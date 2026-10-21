"""Topics, Messages and the Inbox, by a Team's slug and a Topic's number (decisions 0006, 0007,
0024, 0025, 0026).

The operations here serve both the paths of decision 0025 and, through ``api.legacy``, the
former paths of plugins older than 0.5.0, which stay for one more release.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from coloqo_server.api.teams import SHOWN, find_area, online, team_for
from coloqo_server.events import add_event
from coloqo_server.models import (
    Area,
    Assistant,
    File,
    HumanPart,
    Member,
    Message,
    MessageKind,
    Participant,
    Project,
    Team,
    Topic,
    TopicStatus,
    User,
)
from coloqo_server.security import (
    DB,
    Actor,
    ActorDep,
    now,
    pushed_teams,
    require_reader,
    require_writer,
)

router = APIRouter(tags=["topics"])

UNREAD_LIMIT = 20
"""A refused message brings at most this many unread Messages (decision 0007)."""

FEED_LIMIT = 500
"""The most Messages one request returns."""


def ref(number: int) -> str:
    """Return the short reference of a Topic in its Team.

    Args:
        number: The Topic's number.
    """
    return f"T-{number}"


class FileOut(BaseModel):
    """A file shared in a Topic.

    Attributes:
        number: Its number in the Team, ``file 3`` (decision 0025).
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

    number: int
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
        kind: A turn, a progress note, or a service line (stage, closing, taking over).
        author: Pseudonym of the User on whose behalf it is written.
        assistant: Name of the Assistant that wrote it; ``None`` when the human wrote it.
        assistant_key: Its key.
        to: Pseudonym of the addressee; ``None`` for everyone in the Topic.
        to_assistant: Name of the addressed Assistant, if a specific one.
        meant_for: Name of the Assistant it was meant for, when that session was offline and
            the Message went to its person (decision 0029).
        human_part: The human's part in an Assistant's reply (decision 0026); ``None`` for a
            human's own Message, service lines, progress notes and older replies.
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
    assistant_key: str | None
    to: str | None
    to_assistant: str | None
    meant_for: str | None = None
    human_part: HumanPart | None
    reply_to: int | None
    by_holder: bool
    system: bool
    body: str
    files: list[FileOut]
    created_at: datetime


class TopicOut(BaseModel):
    """A Topic in a list.

    Attributes:
        team: The Team's slug.
        number: Its number in the Team.
        ref: Short reference, ``T-<number>``.
        area: The Area's slug.
        area_name: The Area's name.
        title: The question.
        issue: Tracker issue key or link.
        status: Open or closed.
        outcome: How it was settled.
        holder: Name of the holding Assistant.
        holder_key: Its key.
        created_by: Pseudonym of whoever opened it.
        last_number: Number of the newest Message.
        turns_since_human: Assistants' turns since the last human Message.
        turn_limit: The Team's limit of such turns.
        unread: Messages the caller has not read, if they take part.
        addressed: Some unread Message is addressed to the caller.
        addressed_via: When the newest such Message is addressed to one of the caller's
            Assistants, its name: the question is that session's (decision 0029).
        addressed_via_key: Its key.
        created_at: Creation time.
        updated_at: Time of the newest Message.
        closed_at: When it was closed; ``None`` while open.
        deletes_at: When its conversation will be deleted, while it is in the archive.
        deleted_at: When its conversation was deleted; the rest is its card (decision 0021).
    """

    team: str
    number: int
    ref: str
    area: str
    area_name: str
    title: str
    issue: str
    status: TopicStatus
    outcome: str
    holder: str | None
    holder_key: str | None
    created_by: str | None
    last_number: int
    turns_since_human: int
    turn_limit: int
    unread: int
    addressed: bool
    addressed_via: str | None = None
    addressed_via_key: str | None = None
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None
    deletes_at: datetime | None
    deleted_at: datetime | None


class TopicDetail(TopicOut):
    """A Topic with some of its Messages.

    Attributes:
        messages: The Messages asked for, oldest first.
        files: All files shared in the Topic.
    """

    messages: list[MessageOut]
    files: list[FileOut]


class TopicIn(BaseModel):
    """A new Topic with its first Message.

    Attributes:
        area: The Area's slug.
        title: The question, one line.
        body: The first Message: what is asked or which task was started.
        issue: Tracker issue key or link, if the Topic is for one.
        to: Pseudonym of a Member or an Assistant's name, if the first Message is for them.
        with_human: The Assistant's human asked for this Message or saw its text (0026).
    """

    area: str = Field(min_length=1, max_length=40)
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=50_000)
    issue: str = Field(default="", max_length=300)
    to: str | None = None
    with_human: bool = False


class MessageIn(BaseModel):
    """A new Message.

    Attributes:
        number: The number the writer believes is next: the Topic's ``last_number + 1``.
        body: Markdown text.
        kind: ``message`` — a turn; ``progress`` — the holder's note on its own work. Service
            lines have their own operations.
        to: Pseudonym of a Member or an Assistant's name; empty for everyone in the Topic.
        files: Numbers of files uploaded to this Topic to attach.
        as_human: The Assistant relays its human's own words; resets the turn count.
        with_human: The Assistant's human asked for this Message or saw its text (0026).
        reply_to: Number of an earlier Message of the Topic this one answers.
    """

    number: int = Field(ge=1)
    body: str = Field(min_length=1, max_length=50_000)
    kind: MessageKind = MessageKind.Message
    to: str | None = None
    files: list[int] = Field(default_factory=list, max_length=20)
    as_human: bool = False
    with_human: bool = False
    reply_to: int | None = Field(default=None, ge=1)

    @field_validator("kind")
    @classmethod
    def _plain_kind(cls, kind: MessageKind) -> MessageKind:
        """Refuse service lines here: they go through their own operations.

        Args:
            kind: The requested kind.

        Raises:
            ValueError: For ``stage``, ``closed`` or ``taken``.
        """
        if kind not in (MessageKind.Message, MessageKind.Progress):
            raise ValueError("kind is message or progress; a stage goes to /stage")
        return kind


class StageIn(BaseModel):
    """The holder's work turned to a different kind of activity (decisions 0021, 0023).

    Attributes:
        text: One line, e.g. "code in billing and api" or "MR !17 open".
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


@dataclass
class Who:
    """What events and views tell about an Assistant.

    Attributes:
        id: Its database id, for plugins older than 0.5.0 only.
        key: Its public key.
        name: Its shown name.
        project: Its project's key, so the project's other sessions know it (decision 0024).
    """

    id: int
    key: str
    name: str
    project: str


async def assistants_by_id(db: AsyncSession, ids: set[int | None]) -> dict[int, Who]:
    """Return what to show of Assistants, by id.

    Args:
        db: Database session.
        ids: The Assistants.
    """
    wanted = ids - {None}
    if not wanted:
        return {}
    rows = await db.execute(
        select(Assistant, Project.key)
        .join(Project, Project.id == Assistant.project_id)
        .where(Assistant.id.in_(wanted))
    )
    return {a.id: Who(a.id, a.key, a.name, project) for a, project in rows}


async def pseudonyms(db: AsyncSession, ids: set[int | None]) -> dict[int, str | None]:
    """Return pseudonyms by User id.

    Args:
        db: Database session.
        ids: The Users.
    """
    wanted = ids - {None}
    if not wanted:
        return {}
    return {u.id: u.pseudonym for u in await db.scalars(select(User).where(User.id.in_(wanted)))}


def stored(new: dict, old: dict) -> dict:
    """Return an event's data in both shapes: plugins older than 0.5.0 get ``legacy``.

    Args:
        new: The data of decision 0025.
        old: The former data, with database ids.
    """
    return {**new, "legacy": old}


def topic_head(topic: Topic, team: Team, area: Area | None) -> tuple[dict, dict]:
    """Return what every event about a Topic carries, in both shapes.

    Args:
        topic: The Topic.
        team: Its Team.
        area: Its Area.
    """
    new = {
        "team": team.slug,
        "topic": topic.number,
        "ref": ref(topic.number),
        "title": topic.title,
        "area": area.name if area else "",
    }
    old = {
        "topic_id": topic.id,
        "ref": f"T-{topic.id}",
        "title": topic.title,
        "team_id": topic.team_id,
        "area": area.name if area else "",
    }
    return new, old


async def topic_outs(
    db: AsyncSession,
    topics: list[Topic],
    user_id: int,
    archive_days: int,
    assistant_id: int | None = None,
) -> list[TopicOut]:
    """Build the list view of Topics for a User.

    Args:
        db: Database session.
        topics: The Topics.
        user_id: The caller, for unread counts.
        archive_days: The instance's days in the archive, for Teams without their own.
        assistant_id: The calling Assistant, whose own Messages are not another session's.
    """
    if not topics:
        return []
    ids = [topic.id for topic in topics]
    areas = {
        area.id: area
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
    users = await pseudonyms(db, {t.created_by for t in topics})
    holders = await assistants_by_id(db, {t.holder_assistant_id for t in topics})
    # Whom of the caller's the unread Messages addressed to them went to, by Topic, in order.
    targets: dict[int, list[int | None]] = {}
    addressed = [p.topic_id for p in reads.values() if p.addressed]
    if addressed:
        rows = await db.execute(
            select(Message.topic_id, Message.to_assistant_id)
            .join(Participant, Participant.topic_id == Message.topic_id)
            .where(
                Message.topic_id.in_(addressed),
                Participant.user_id == user_id,
                Message.to_user_id == user_id,
                Message.number > Participant.last_read,
            )
            .order_by(Message.topic_id, Message.number)
        )
        for topic_id, target in rows:
            targets.setdefault(topic_id, []).append(target)
    # A question to the person, or to the calling session, is the caller's own; otherwise the
    # newest one names the session that answers it (decision 0029).
    newest = {
        topic_id: found[-1]
        for topic_id, found in targets.items()
        if None not in found and (assistant_id is None or assistant_id not in found)
    }
    via = await assistants_by_id(db, set(newest.values()))
    result = []
    for topic in topics:
        read = reads.get(topic.id)
        unread = topic.last_number - read.last_read if read else 0
        through = via.get(newest.get(topic.id) or 0)
        team = teams[topic.team_id]
        area = areas.get(topic.area_id)
        holder = holders.get(topic.holder_assistant_id or 0)
        days = team.archive_days or archive_days
        result.append(
            TopicOut(
                team=team.slug,
                number=topic.number,
                ref=ref(topic.number),
                area=area.slug if area else "",
                area_name=area.name if area else "",
                title=topic.title,
                issue=topic.issue,
                status=topic.status,
                outcome=topic.outcome,
                holder=holder.name if holder else None,
                holder_key=holder.key if holder else None,
                created_by=users.get(topic.created_by),
                last_number=topic.last_number,
                turns_since_human=topic.turns_since_human,
                turn_limit=team.turn_limit,
                unread=max(unread, 0),
                addressed=bool(read and read.addressed and unread > 0),
                addressed_via=through.name if through and unread > 0 else None,
                addressed_via_key=through.key if through and unread > 0 else None,
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


async def file_outs(db: AsyncSession, files: list[File], preview_max_bytes: int) -> list[FileOut]:
    """Build the view of files.

    Args:
        db: Database session.
        files: The files.
        preview_max_bytes: Largest image shown inline.
    """
    users = await pseudonyms(db, {f.uploaded_by for f in files})
    numbers = {
        message.id: message.number
        for message in await db.scalars(
            select(Message).where(Message.id.in_({f.message_id for f in files} - {None}))
        )
    }
    return [
        FileOut(
            number=f.number,
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


async def message_outs(
    db: AsyncSession, messages: list[Message], files: list[FileOut], file_rows: list[File]
) -> list[MessageOut]:
    """Build the view of Messages with their attached files.

    Args:
        db: Database session.
        messages: The Messages.
        files: Views of the Topic's files.
        file_rows: The same files as rows, to match them to Messages.
    """
    users = await pseudonyms(
        db, {m.author_user_id for m in messages} | {m.to_user_id for m in messages}
    )
    assistants = await assistants_by_id(
        db,
        {m.author_assistant_id for m in messages}
        | {m.to_assistant_id for m in messages}
        | {m.meant_for_id for m in messages},
    )
    by_message: dict[int, list[FileOut]] = {}
    for row, view in zip(file_rows, files, strict=True):
        if row.message_id is not None:
            by_message.setdefault(row.message_id, []).append(view)
    result = []
    for m in messages:
        author = assistants.get(m.author_assistant_id or 0)
        to = assistants.get(m.to_assistant_id or 0)
        result.append(
            MessageOut(
                number=m.number,
                kind=m.kind,
                author=users.get(m.author_user_id),
                assistant=author.name if author else None,
                assistant_key=author.key if author else None,
                to=users.get(m.to_user_id or 0),
                to_assistant=to.name if to else None,
                meant_for=meant.name if (meant := assistants.get(m.meant_for_id or 0)) else None,
                human_part=m.human_part,
                reply_to=m.reply_to,
                by_holder=m.by_holder,
                system=m.system,
                body=m.body,
                files=by_message.get(m.id, []),
                created_at=m.created_at,
            )
        )
    return result


async def check_topic(
    db: AsyncSession, topic: Topic | None, actor: Actor, label: str, write: bool
) -> Topic:
    """Check a found Topic against the caller: membership, and the right to write.

    Args:
        db: Database session.
        topic: The Topic found, or ``None``.
        actor: The caller.
        label: How the Topic was named, for the refusal.
        write: The caller is about to change the Topic: an Assistant must be linked to its
            Team (decision 0020), and a deleted Topic is only a card.

    Raises:
        HTTPException: 404 when there is no such Topic in the caller's Teams; 403 when the
            caller may not write there; 410 to write into a deleted Topic.
    """
    require_reader(actor)
    if topic is None or await db.get(Member, (topic.team_id, actor.user.id)) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No such Topic {label}")
    if write:
        await require_writer(db, actor, topic.team_id)
        if topic.deleted_at is not None:
            raise HTTPException(
                status.HTTP_410_GONE,
                f"{label} was closed and its conversation deleted; open a new Topic",
            )
    return topic


async def topic_for(
    db: AsyncSession,
    team: str,
    number: int,
    actor: Actor,
    lock: bool = False,
    write: bool = False,
) -> tuple[Topic, Team]:
    """Return a Topic by its Team's slug and its number.

    Args:
        db: Database session.
        team: The Team's slug, current or former.
        number: The Topic's number in the Team.
        actor: The caller.
        lock: Lock the row until the transaction ends, to number a new Message.
        write: The caller is about to change the Topic.

    Raises:
        HTTPException: 404 when there is no such Topic in the caller's Teams; 403 when the
            caller may not write there; 410 to write into a deleted Topic.
    """
    require_reader(actor)
    found, _ = await team_for(db, team, actor.user.id)
    query = select(Topic).where(Topic.team_id == found.id, Topic.number == number)
    topic = await db.scalar(query.with_for_update() if lock else query)
    return await check_topic(db, topic, actor, f"{found.slug}/{ref(number)}", write), found


async def addressee(
    db: AsyncSession, team_id: int, to: str | None
) -> tuple[int | None, int | None, int | None]:
    """Resolve whom a Message is addressed to in a Team: the User, the Assistant, and the
    Assistant it was meant for when that one is offline.

    An Assistant is named by its full name; a name without its word (``alice · web``, as plugins
    before sessions knew it) reaches the project's most recently active Assistant. A Message to
    an Assistant whose session is not online goes to its person, and every online session of
    the person sees it (decision 0029).

    Args:
        db: Database session.
        team_id: The Team.
        to: A Member's pseudonym or an Assistant's name, any case; empty for everyone.

    Raises:
        HTTPException: 422 when nobody in the Team has this name; the detail lists the
            names that would work.
    """
    if not to or not to.strip():
        return None, None, None
    name = to.strip().lstrip("@").lower()
    members = list(
        await db.scalars(
            select(User).join(Member, Member.user_id == User.id).where(Member.team_id == team_id)
        )
    )
    for user in members:
        if user.pseudonym and user.pseudonym.lower() == name:
            return user.id, None, None
    # Only Assistants whose project is linked to this Team take part in it (decision 0020).
    assistants = list(
        await db.scalars(
            select(Assistant)
            .join(Project, Project.id == Assistant.project_id)
            .where(Assistant.user_id.in_([u.id for u in members]), Project.team_id == team_id)
            .order_by(Assistant.last_seen_at.desc().nulls_last())
        )
    )
    found = next((a for a in assistants if a.name.lower() == name), None) or next(
        (a for a in assistants if a.name.lower().rpartition(" · ")[0] == name), None
    )
    if found is not None:
        if online(found):
            return found.user_id, found.id, None
        return found.user_id, None, found.id
    shown = [a.name for a in assistants if a.last_seen_at and a.last_seen_at > now() - SHOWN]
    known = sorted([u.pseudonym for u in members if u.pseudonym] + shown)
    raise HTTPException(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        f"Nobody in the Team is called {to!r}. Members and Assistants: {', '.join(known)}",
    )


async def join(db: AsyncSession, topic_id: int, user_ids: set[int | None]) -> None:
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


def human_part(
    actor: Actor, kind: MessageKind, as_human: bool, with_human: bool
) -> HumanPart | None:
    """Return the mark of a Message by who wrote it and what the Assistant declared (0026).

    A human's own Message, a progress note and a service line carry none. A plugin older than
    0.5.0 cannot declare "with", so its replies stay unmarked unless they relay the human's
    words.

    Args:
        actor: The writer.
        kind: The Message's kind.
        as_human: The Assistant relays its human's words.
        with_human: The Assistant's human asked for this Message or saw its text.
    """
    if actor.assistant is None or kind != MessageKind.Message:
        return None
    if as_human:
        return HumanPart.Words
    if actor.legacy:
        return None
    return HumanPart.With if with_human else HumanPart.Without


async def post(
    db: AsyncSession,
    actor: Actor,
    topic: Topic,
    body: str,
    kind: MessageKind,
    to: str | None,
    files: list[File],
    as_human: bool = False,
    with_human: bool = False,
    counts_as_turn: bool = True,
    extra: tuple[dict, dict] | None = None,
) -> tuple[Message, set[int]]:
    """Write the next Message into a locked Topic and queue its events.

    Args:
        db: Database session, with the Topic row locked.
        actor: The writer.
        topic: The Topic.
        body: Text.
        kind: Turn, progress note or service line.
        to: Addressee name, if any.
        files: Files of the Topic, not attached yet, to attach.
        as_human: The Assistant relays its human's words.
        with_human: The Assistant's human asked for this Message or saw its text.
        counts_as_turn: An Assistant's Message counts against the turn limit; the opening
            Message of a Topic does not.
        extra: More event data, in the new and the former shape.

    Raises:
        HTTPException: 422 for an unknown addressee; 409 when the Topic waits for a human
            (decision 0007).
    """
    to_user_id, to_assistant_id, meant_for_id = await addressee(db, topic.team_id, to)
    human = actor.is_human or as_human
    team = await db.get(Team, topic.team_id)
    assert team is not None
    if human:
        topic.turns_since_human = 0
    elif kind == MessageKind.Message and counts_as_turn:
        if topic.turns_since_human >= team.turn_limit:
            label = f"T-{topic.id}" if actor.legacy else ref(topic.number)
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                {
                    "code": "turn_limit",
                    "message": (
                        f"{label} has reached {team.turn_limit} Assistants' turns without "
                        "a human, and waits for one. Ask your human: they can write in the Topic "
                        "in the web interface, or tell you what to post, and you post their words "
                        "with as_human=true."
                    ),
                },
            )
        topic.turns_since_human += 1
    topic.last_number += 1
    topic.updated_at = now()
    topic.idle_warned_at = None
    if topic.status == TopicStatus.Closed and kind in (
        MessageKind.Message,
        MessageKind.Stage,
        MessageKind.Taken,
    ):
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
        meant_for_id=meant_for_id,
        relayed=bool(as_human and actor.assistant is not None),
        human_part=human_part(actor, kind, as_human, with_human),
        by_holder=actor.assistant is not None and actor.assistant.id == topic.holder_assistant_id,
        body=body,
    )
    db.add(message)
    await db.flush()
    for file in files:
        file.message_id = message.id
    await join(db, topic.id, {actor.user.id, to_user_id})
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
    involved = posters | {topic.holder_assistant_id, to_assistant_id}
    who = await assistants_by_id(db, involved | {meant_for_id})
    holder = who.get(topic.holder_assistant_id or 0)
    users = await pseudonyms(db, {to_user_id})
    area = await db.get(Area, topic.area_id)
    new, old = topic_head(topic, team, area)
    author = who.get(message.author_assistant_id or 0)
    new |= {
        "number": message.number,
        "kind": kind.value,
        "author": actor.user.pseudonym,
        "assistant": author.name if author else None,
        "author_assistant": author.key if author else None,
        "human": human,
        "to": users.get(to_user_id or 0),
        "to_assistant": who[to_assistant_id].key if to_assistant_id in who else None,
        "to_assistant_name": who[to_assistant_id].name if to_assistant_id in who else None,
        "meant_for": who[meant_for_id].name if meant_for_id in who else None,
        "holder": holder.key if holder else None,
        "holder_project": holder.project if holder else None,
        "assistants": sorted(who[i].key for i in posters | {topic.holder_assistant_id} if i in who),
    }
    old |= {
        "number": message.number,
        # Plugins before 0.5.0 know no "taken" line; as a stage line they leave it out.
        "kind": MessageKind.Stage.value if kind == MessageKind.Taken else kind.value,
        "author": actor.user.pseudonym,
        "author_user_id": actor.user.id,
        "author_assistant_id": message.author_assistant_id,
        "assistant": author.name if author else None,
        "human": human,
        "to_user_id": to_user_id,
        "to_assistant_id": to_assistant_id,
        "holder_assistant_id": topic.holder_assistant_id,
        "assistant_ids": sorted(posters | {topic.holder_assistant_id} - {None}),
    }
    if extra:
        new |= extra[0]
        old |= extra[1]
    recipients = await add_event(db, topic.team_id, "message", stored(new, old))
    return message, recipients


async def attachable(db: AsyncSession, topic: Topic, numbers: list[int]) -> list[File]:
    """Return files of a Topic by their numbers in the Team, if none is attached yet.

    Args:
        db: Database session.
        topic: The Topic.
        numbers: The files' numbers.

    Raises:
        HTTPException: 422 for files not in this Topic or already attached.
    """
    if not numbers:
        return []
    files = list(
        await db.scalars(
            select(File).where(
                File.team_id == topic.team_id,
                File.number.in_(numbers),
                File.topic_id == topic.id,
                File.message_id.is_(None),
            )
        )
    )
    if len(files) != len(set(numbers)):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Attach only files uploaded to this Topic and not attached to another Message",
        )
    return files


async def open_topic(
    db: AsyncSession,
    actor: Actor,
    area: Area,
    title: str,
    body: str,
    issue: str,
    to: str | None,
    with_human: bool,
) -> tuple[Topic, set[int]]:
    """Open a Topic with its first Message; the calling Assistant holds it.

    The Topic takes the next number of its Team under a lock on the Team's row, so numbers
    have no gaps (decision 0025).

    Args:
        db: Database session.
        actor: The caller, already allowed to write in the Area's Team.
        area: The Area.
        title: The question.
        body: The first Message.
        issue: Tracker issue key or link.
        to: Addressee of the first Message.
        with_human: The Assistant's human asked for it or saw its text.

    Raises:
        HTTPException: 422 for an unknown addressee.
    """
    team = await db.scalar(select(Team).where(Team.id == area.team_id).with_for_update())
    assert team is not None
    team.last_topic += 1
    topic = Topic(
        team_id=team.id,
        number=team.last_topic,
        area_id=area.id,
        title=title.strip(),
        issue=issue.strip(),
        status=TopicStatus.Open,
        outcome="",
        created_by=actor.user.id,
        holder_assistant_id=actor.assistant.id if actor.assistant else None,
        last_number=0,
        turns_since_human=0,
    )
    to_user_id, to_assistant_id, meant_for_id = await addressee(db, team.id, to)
    db.add(topic)
    await db.flush()
    who = await assistants_by_id(db, {topic.holder_assistant_id, to_assistant_id, meant_for_id})
    users = await pseudonyms(db, {to_user_id})
    holder = who.get(topic.holder_assistant_id or 0)
    new, old = topic_head(topic, team, area)
    new |= {
        "author": actor.user.pseudonym,
        "author_assistant": holder.key if holder else None,
        "holder": holder.key if holder else None,
        "to": users.get(to_user_id or 0),
        "to_assistant": who[to_assistant_id].key if to_assistant_id in who else None,
        "to_assistant_name": who[to_assistant_id].name if to_assistant_id in who else None,
        "meant_for": who[meant_for_id].name if meant_for_id in who else None,
    }
    old |= {
        "author": actor.user.pseudonym,
        "author_user_id": actor.user.id,
        "author_assistant_id": topic.holder_assistant_id,
        "holder_assistant_id": topic.holder_assistant_id,
        "to_user_id": to_user_id,
        "to_assistant_id": to_assistant_id,
    }
    recipients = await add_event(db, team.id, "topic", stored(new, old))
    # The opening Message is not a turn: the conversation starts with it.
    _, more = await post(
        db,
        actor,
        topic,
        body,
        MessageKind.Message,
        to,
        [],
        with_human=with_human,
        counts_as_turn=False,
    )
    return topic, recipients | more


async def hold(db: AsyncSession, actor: Actor, topic: Topic) -> set[int]:
    """Make the calling Assistant the holder of a locked Topic (decisions 0006, 0024).

    Taking a Topic over from another Assistant leaves a service line in the feed: "lyra took
    T-12 from vega"; holding one that nobody holds leaves "lyra took T-12".

    Args:
        db: Database session, with the Topic row locked.
        actor: The Assistant.
        topic: The Topic.

    Raises:
        HTTPException: 403 without an Assistant.
    """
    if actor.assistant is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only an Assistant holds a Topic")
    if topic.holder_assistant_id == actor.assistant.id:
        return set()
    former = await assistants_by_id(db, {topic.holder_assistant_id})
    was = former.get(topic.holder_assistant_id or 0)
    topic.holder_assistant_id = actor.assistant.id
    await join(db, topic.id, {actor.user.id})
    _, recipients = await post(
        db,
        actor,
        topic,
        was.name if was else "",
        MessageKind.Taken,
        None,
        [],
        extra=({"from": was.key if was else None}, {}),
    )
    return recipients


async def note_stage(
    db: AsyncSession, actor: Actor, topic: Topic, text: str, label: str
) -> tuple[Message, set[int]]:
    """Note that the holder's work turned to a different kind of activity (decision 0021).

    Args:
        db: Database session, with the Topic row locked.
        actor: The holding Assistant.
        topic: The Topic.
        text: The stage, one line.
        label: How the caller names the Topic, for the refusal.

    Raises:
        HTTPException: 409 ``not_holder`` unless the caller is the holding Assistant.
    """
    if actor.assistant is None or actor.assistant.id != topic.holder_assistant_id:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "code": "not_holder",
                "message": f"Only the Assistant holding {label} notes its stages; "
                "take it over with hold_topic first if the task is yours.",
            },
        )
    return await post(db, actor, topic, text.strip(), MessageKind.Stage, None, [])


async def settle(
    db: AsyncSession, actor: Actor, topic: Topic, body: TopicPatch, label: str
) -> set[int]:
    """Close a locked Topic with an outcome, or reopen it (decision 0021).

    The holding Assistant closes its Topic, and so does any human of the Team; only a human
    reopens one this way, an Assistant does it by writing in it.

    Args:
        db: Database session, with the Topic row locked.
        actor: The holding Assistant or a human of the Team.
        topic: The Topic.
        body: New state and outcome.
        label: How the caller names the Topic, for refusals.

    Raises:
        HTTPException: 403 for an Assistant reopening; 409 ``not_holder`` for an Assistant that
            does not hold it; 422 for an Assistant closing without an outcome.
    """
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
                    "message": f"Only the Assistant holding {label}, or a human, closes it; "
                    "take it over with hold_topic first if the task is yours, or tell the "
                    "holder it can be closed.",
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
        _, recipients = await post(db, actor, topic, topic.outcome, MessageKind.Closed, None, [])
        topic.closed_at = now()
    elif body.status == TopicStatus.Open:
        topic.closed_at = None
        topic.idle_warned_at = None
    topic.status = body.status
    topic.updated_at = now()
    team = await db.get(Team, topic.team_id)
    area = await db.get(Area, topic.area_id)
    assert team is not None
    who = await assistants_by_id(
        db, {topic.holder_assistant_id, actor.assistant.id if actor.assistant else None}
    )
    holder = who.get(topic.holder_assistant_id or 0)
    author = who.get(actor.assistant.id) if actor.assistant else None
    new, old = topic_head(topic, team, area)
    new |= {
        "status": topic.status.value,
        "author": author.name if author else actor.user.pseudonym,
        "author_assistant": author.key if author else None,
        "holder": holder.key if holder else None,
        "holder_project": holder.project if holder else None,
        "outcome": topic.outcome,
        "automatic": False,
    }
    old |= {
        "status": topic.status.value,
        "author": author.name if author else actor.user.pseudonym,
        "author_assistant_id": actor.assistant.id if actor.assistant else None,
        "holder_assistant_id": topic.holder_assistant_id,
        "outcome": topic.outcome,
        "automatic": False,
    }
    recipients |= await add_event(db, topic.team_id, "topic_status", stored(new, old))
    return recipients


async def mark_read(db: AsyncSession, actor: Actor, topic: Topic, number: int) -> None:
    """Record how far the caller has read a Topic; it leaves the Inbox when read through.

    An Assistant reading another Team's Topic marks nothing: that Team's Inbox stays as it was
    (decision 0020).

    Args:
        db: Database session.
        actor: The caller.
        topic: The Topic.
        number: Number of the newest Message read.
    """
    scope = pushed_teams(actor)
    if scope is not None and topic.team_id not in scope:
        return
    number = min(number, topic.last_number)
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


async def feed(
    db: AsyncSession,
    actor: Actor,
    topic: Topic,
    after: int | None,
    before: int | None,
    limit: int,
    from_unread: bool,
) -> list[Message]:
    """Return the Messages a reader asked for, oldest first (decision 0026).

    ``before`` gives the last ``limit`` Messages with a smaller number; ``after`` the first
    ``limit`` with a greater one; ``from_unread`` starts at the caller's first unread Message
    when more than ``limit`` are unread, at most 500 back; otherwise the last ``limit``.

    Args:
        db: Database session.
        actor: The caller.
        topic: The Topic.
        after: Only Messages with a greater number.
        before: Only Messages with a smaller number.
        limit: How many.
        from_unread: Start at the first unread Message when that shows more.
    """
    query = select(Message).where(Message.topic_id == topic.id)
    if before is not None:
        rows = await db.scalars(
            query.where(Message.number < before).order_by(Message.number.desc()).limit(limit)
        )
        return list(reversed(list(rows)))
    if after is not None:
        rows = await db.scalars(
            query.where(Message.number > after).order_by(Message.number).limit(limit)
        )
        return list(rows)
    if from_unread:
        read = await db.get(Participant, (topic.id, actor.user.id))
        unread = topic.last_number - read.last_read if read else 0
        limit = min(max(limit, unread), FEED_LIMIT)
    rows = await db.scalars(query.order_by(Message.number.desc()).limit(limit))
    return list(reversed(list(rows)))


async def topic_detail(
    request: Request, db: AsyncSession, actor: Actor, topic: Topic, messages: list[Message]
) -> TopicDetail:
    """Build a Topic with the given Messages and all its files.

    Args:
        request: The incoming request, for the instance's settings.
        db: Database session.
        actor: The caller.
        topic: The Topic.
        messages: Its Messages to show.
    """
    settings = request.app.state.settings
    file_rows = list(
        await db.scalars(select(File).where(File.topic_id == topic.id).order_by(File.number))
    )
    files = await file_outs(db, file_rows, settings.preview_max_bytes)
    (summary,) = await topic_outs(
        db,
        [topic],
        actor.user.id,
        settings.archive_days,
        actor.assistant.id if actor.assistant else None,
    )
    return TopicDetail(
        **summary.model_dump(),
        messages=await message_outs(db, messages, files, file_rows),
        files=files,
    )


async def number_taken(
    request: Request, db: AsyncSession, topic: Topic, number: int, label: str, legacy: bool
) -> JSONResponse:
    """Refuse a Message whose number is not next, with the Messages the writer missed (0007).

    Args:
        request: The incoming request, for the instance's settings.
        db: Database session; rolled back here.
        topic: The Topic.
        number: The number the writer sent.
        label: How the caller names the Topic.
        legacy: Show the Messages the way plugins older than 0.5.0 read them.
    """
    unread_rows = list(
        await db.scalars(
            select(Message)
            .where(Message.topic_id == topic.id, Message.number >= number)
            .order_by(Message.number)
            .limit(UNREAD_LIMIT + 1)
        )
    )
    file_rows = list(await db.scalars(select(File).where(File.topic_id == topic.id)))
    if legacy:
        from coloqo_server.api.legacy import legacy_messages

        unread = await legacy_messages(
            db, unread_rows[:UNREAD_LIMIT], file_rows, request.app.state.settings
        )
    else:
        files = await file_outs(db, file_rows, request.app.state.settings.preview_max_bytes)
        unread = await message_outs(db, unread_rows[:UNREAD_LIMIT], files, file_rows)
    too_many = len(unread_rows) > UNREAD_LIMIT
    next_number = topic.last_number + 1
    await db.rollback()
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "detail": {
                "code": "number_taken",
                "message": (
                    f"Message {number} is not next in {label}: the next number is {next_number}. "
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


@router.get("/team/{team}/topic")
async def list_topics(
    request: Request,
    team: str,
    actor: ActorDep,
    db: DB,
    area: Annotated[str | None, Query()] = None,
    status_filter: Annotated[TopicStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[TopicOut]:
    """List a Team's Topics, newest activity first; deleted ones are left out.

    Args:
        request: The incoming request.
        team: The Team's slug.
        actor: The caller.
        db: Database session.
        area: Only this Area, by slug.
        status_filter: Only open or only closed.
        limit: At most this many.

    Raises:
        HTTPException: 404 when the caller is not in the Team or there is no such Area; 403 for
            a plugin request without an Assistant.
    """
    require_reader(actor)
    found, _ = await team_for(db, team, actor.user.id)
    query = select(Topic).where(Topic.team_id == found.id, Topic.deleted_at.is_(None))
    if area is not None:
        row = await find_area(db, found.id, area)
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No such Area")
        query = query.where(Topic.area_id == row.id)
    if status_filter is not None:
        query = query.where(Topic.status == status_filter)
    topics = list(await db.scalars(query.order_by(Topic.updated_at.desc()).limit(limit)))
    return await topic_outs(
        db,
        topics,
        actor.user.id,
        request.app.state.settings.archive_days,
        actor.assistant.id if actor.assistant else None,
    )


@router.post("/team/{team}/topic", status_code=status.HTTP_201_CREATED)
async def create_topic(
    request: Request, team: str, body: TopicIn, actor: ActorDep, db: DB
) -> TopicDetail:
    """Open a Topic in an Area with its first Message; the calling Assistant holds it.

    Args:
        request: The incoming request.
        team: The Team's slug.
        body: Area, title and first Message.
        actor: The caller.
        db: Database session.

    Raises:
        HTTPException: 404 when there is no such Team or Area for the caller; 403 when the
            caller may not write there (decision 0020); 422 for an unknown addressee.
    """
    require_reader(actor)
    found, _ = await team_for(db, team, actor.user.id)
    area = await find_area(db, found.id, body.area)
    if area is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No Area {body.area!r} in the Team")
    await require_writer(db, actor, found.id)
    topic, recipients = await open_topic(
        db, actor, area, body.title, body.body, body.issue, body.to, body.with_human
    )
    await db.commit()
    request.app.state.bus.wake(recipients)
    messages = await feed(db, actor, topic, None, None, 50, False)
    return await topic_detail(request, db, actor, topic, messages)


@router.get("/team/{team}/topic/{number}")
async def read_topic(
    request: Request,
    team: str,
    number: int,
    actor: ActorDep,
    db: DB,
    after: Annotated[int | None, Query(ge=0)] = None,
    before: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=FEED_LIMIT)] = 50,
    from_unread: Annotated[bool, Query()] = False,
) -> TopicDetail:
    """Return a Topic with some of its Messages (decisions 0007, 0026).

    Without ``after`` or ``before``: its last ``limit`` Messages, or with ``from_unread`` from
    the caller's first unread one, at most 500.

    Args:
        request: The incoming request.
        team: The Team's slug.
        number: The Topic's number.
        actor: The caller.
        db: Database session.
        after: Only Messages with a greater number, the first ``limit`` of them.
        before: Only Messages with a smaller number, the last ``limit`` of them.
        limit: How many Messages.
        from_unread: Start at the first unread Message when more than ``limit`` are unread.

    Raises:
        HTTPException: 404 when there is no such Topic in the caller's Teams; 403 for a
            plugin request without an Assistant.
    """
    topic, _ = await topic_for(db, team, number, actor)
    messages = await feed(db, actor, topic, after, before, limit, from_unread)
    return await topic_detail(request, db, actor, topic, messages)


@router.post("/team/{team}/topic/{number}/message", status_code=status.HTTP_201_CREATED)
async def post_message(
    request: Request, team: str, number: int, body: MessageIn, actor: ActorDep, db: DB
) -> MessageOut:
    """Write a Message with the number the writer believes is next (decision 0007).

    Args:
        request: The incoming request.
        team: The Team's slug.
        number: The Topic's number.
        body: The Message.
        actor: The writer.
        db: Database session.

    Raises:
        HTTPException: 404 when there is no such Topic; 403 when the caller may not write
            there (decision 0020); 410 for a deleted Topic; 409 ``number_taken`` with the
            unread Messages when the number is not next, or ``turn_limit`` when the Topic
            waits for a human; 422 for an unknown addressee, foreign files or a ``reply_to``
            that is not an earlier Message of the Topic.
    """
    topic, found = await topic_for(db, team, number, actor, lock=True, write=True)
    label = f"{found.slug}/{ref(topic.number)}"
    if body.number != topic.last_number + 1:
        return await number_taken(request, db, topic, body.number, label, legacy=False)
    if body.reply_to is not None and body.reply_to > topic.last_number:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"There is no Message #{body.reply_to} in {label} to reply to",
        )
    files = await attachable(db, topic, body.files)
    message, recipients = await post(
        db,
        actor,
        topic,
        body.body,
        body.kind,
        body.to,
        files,
        as_human=body.as_human,
        with_human=body.with_human,
    )
    message.reply_to = body.reply_to
    await db.commit()
    request.app.state.bus.wake(recipients)
    file_rows = list(await db.scalars(select(File).where(File.message_id == message.id)))
    views = await file_outs(db, file_rows, request.app.state.settings.preview_max_bytes)
    (out,) = await message_outs(db, [message], views, file_rows)
    return out


@router.post("/team/{team}/topic/{number}/hold")
async def hold_topic(request: Request, team: str, number: int, actor: ActorDep, db: DB) -> TopicOut:
    """Make the calling Assistant the Topic's holder; taking over shows in the feed (0024).

    Args:
        request: The incoming request.
        team: The Team's slug.
        number: The Topic's number.
        actor: The Assistant.
        db: Database session.

    Raises:
        HTTPException: 404 when there is no such Topic; 403 without an Assistant, or when
            it may not write there (decision 0020); 410 for a deleted Topic.
    """
    if actor.assistant is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only an Assistant holds a Topic")
    topic, _ = await topic_for(db, team, number, actor, lock=True, write=True)
    recipients = await hold(db, actor, topic)
    await db.commit()
    request.app.state.bus.wake(recipients)
    (out,) = await topic_outs(
        db,
        [topic],
        actor.user.id,
        request.app.state.settings.archive_days,
        actor.assistant.id if actor.assistant else None,
    )
    return out


@router.post("/team/{team}/topic/{number}/stage", status_code=status.HTTP_201_CREATED)
async def post_stage(
    request: Request, team: str, number: int, body: StageIn, actor: ActorDep, db: DB
) -> MessageOut:
    """Note that the holder's work turned to a different kind of activity (decision 0021).

    Takes no number: a stage answers nothing, so it needs no check for unread Messages. It is
    not a turn; it takes the Topic out of the archive, since work goes on.

    Args:
        request: The incoming request.
        team: The Team's slug.
        number: The Topic's number.
        body: The stage.
        actor: The holding Assistant.
        db: Database session.

    Raises:
        HTTPException: 404 when there is no such Topic; 403 when the caller may not write
            there; 409 ``not_holder`` unless the caller is the holding Assistant; 410 for a
            deleted Topic.
    """
    topic, found = await topic_for(db, team, number, actor, lock=True, write=True)
    message, recipients = await note_stage(
        db, actor, topic, body.text, f"{found.slug}/{ref(topic.number)}"
    )
    await db.commit()
    request.app.state.bus.wake(recipients)
    (out,) = await message_outs(db, [message], [], [])
    return out


@router.patch("/team/{team}/topic/{number}")
async def settle_topic(
    request: Request, team: str, number: int, body: TopicPatch, actor: ActorDep, db: DB
) -> TopicOut:
    """Close a Topic with an outcome, or reopen it (decision 0021).

    Args:
        request: The incoming request.
        team: The Team's slug.
        number: The Topic's number.
        body: New state and outcome.
        actor: The holding Assistant or a human of the Team.
        db: Database session.

    Raises:
        HTTPException: 404 when there is no such Topic in the caller's Teams; 403 when the
            caller may not write there or is an Assistant reopening; 409 ``not_holder`` for an
            Assistant that does not hold it; 422 for an Assistant closing without an outcome;
            410 for a deleted Topic.
    """
    topic, found = await topic_for(db, team, number, actor, lock=True, write=True)
    recipients = await settle(db, actor, topic, body, f"{found.slug}/{ref(topic.number)}")
    await db.commit()
    request.app.state.bus.wake(recipients)
    (out,) = await topic_outs(
        db,
        [topic],
        actor.user.id,
        request.app.state.settings.archive_days,
        actor.assistant.id if actor.assistant else None,
    )
    return out


@router.post("/team/{team}/topic/{number}/read")
async def read_up_to(
    request: Request, team: str, number: int, body: ReadIn, actor: ActorDep, db: DB
) -> TopicOut:
    """Record how far the caller has read a Topic; it leaves the Inbox when read through.

    Args:
        request: The incoming request.
        team: The Team's slug.
        number: The Topic's number.
        body: Number of the newest Message read.
        actor: The caller.
        db: Database session.

    Raises:
        HTTPException: 404 when there is no such Topic in the caller's Teams; 403 for a
            plugin request without an Assistant.
    """
    topic, _ = await topic_for(db, team, number, actor)
    await mark_read(db, actor, topic, body.number)
    (out,) = await topic_outs(
        db,
        [topic],
        actor.user.id,
        request.app.state.settings.archive_days,
        actor.assistant.id if actor.assistant else None,
    )
    return out


async def inbox_topics(db: AsyncSession, actor: Actor) -> list[Topic]:
    """Return the Topics the caller takes part in that have unread Messages (decision 0006).

    The Inbox is shared by all of a User's Assistants; an Assistant sees the part of it in the
    Team its project is linked to, and an unlinked one sees nothing (decision 0020).

    Args:
        db: Database session.
        actor: The caller.
    """
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
    return list(
        await db.scalars(
            query.order_by(Participant.addressed.desc(), Topic.updated_at.desc()).limit(100)
        )
    )


@router.get("/inbox", response_model=list[TopicOut])
async def inbox(request: Request, actor: ActorDep, db: DB) -> list[TopicOut] | JSONResponse:
    """List Topics the caller takes part in that have unread Messages (decision 0006).

    The web shows those addressed to the person as "For you" (decision 0026); an agent gets the
    whole list.

    Args:
        request: The incoming request.
        actor: The caller.
        db: Database session.

    Raises:
        HTTPException: 403 for a plugin request without an Assistant.
    """
    require_reader(actor)
    topics = await inbox_topics(db, actor)
    if actor.legacy:
        from coloqo_server.api.legacy import legacy_topics

        return JSONResponse(
            jsonable_encoder(
                await legacy_topics(db, topics, actor.user.id, request.app.state.settings)
            )
        )
    return await topic_outs(
        db,
        topics,
        actor.user.id,
        request.app.state.settings.archive_days,
        actor.assistant.id if actor.assistant else None,
    )
