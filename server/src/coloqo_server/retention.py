"""How long a Topic lives: idle ones close, archived ones lose their conversation (0021)."""

from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from coloqo_server.api.topics import assistants_by_id, stored, topic_head
from coloqo_server.events import add_events
from coloqo_server.models import (
    Area,
    Assistant,
    Event,
    File,
    Member,
    Message,
    MessageKind,
    Participant,
    Team,
    Topic,
    TopicStatus,
)
from coloqo_server.settings import Settings

IDLE_OUTCOME = "Closed for inactivity: no Messages for {days} days."


async def _people(db: AsyncSession, topic: Topic) -> set[int]:
    """Return who should hear about a Topic going idle: its people and its holder's person.

    Args:
        db: Database session.
        topic: The Topic.
    """
    people = set(
        await db.scalars(select(Participant.user_id).where(Participant.topic_id == topic.id))
    )
    holder = await db.get(Assistant, topic.holder_assistant_id or 0)
    return people | ({holder.user_id} if holder else set())


async def _head(db: AsyncSession, topic: Topic) -> tuple[dict, dict]:
    """Return what an event about a Topic carries, in both shapes, with its holder.

    The holder's project goes with it, so the project's other sessions hear about the Topic
    when its holder is gone (decision 0024).

    Args:
        db: Database session.
        topic: The Topic.
    """
    team = await db.get(Team, topic.team_id)
    area = await db.get(Area, topic.area_id)
    assert team is not None
    new, old = topic_head(topic, team, area)
    holder = (await assistants_by_id(db, {topic.holder_assistant_id})).get(
        topic.holder_assistant_id or 0
    )
    new |= {
        "holder": holder.key if holder else None,
        "holder_project": holder.project if holder else None,
    }
    old |= {"holder_assistant_id": topic.holder_assistant_id}
    return new, old


async def warn_idle(db: AsyncSession, settings: Settings, moment: datetime) -> set[int]:
    """Tell the people of Topics about to close for inactivity, once per quiet spell.

    Args:
        db: Database session.
        settings: Instance settings.
        moment: Now.

    Returns:
        The Users who got events, to wake after the commit.
    """
    quiet_since = moment - timedelta(days=settings.idle_close_days - settings.idle_warn_days)
    topics = list(
        await db.scalars(
            select(Topic)
            .where(
                Topic.status == TopicStatus.Open,
                Topic.deleted_at.is_(None),
                Topic.idle_warned_at.is_(None),
                Topic.updated_at < quiet_since,
            )
            .with_for_update(skip_locked=True)
        )
    )
    recipients: set[int] = set()
    for topic in topics:
        topic.idle_warned_at = moment
        closes_at = topic.updated_at + timedelta(days=settings.idle_close_days)
        new, old = await _head(db, topic)
        new["closes_at"] = old["closes_at"] = closes_at.isoformat()
        recipients |= add_events(
            db, await _people(db, topic), "topic_idle", stored(new, old, topic.team_id)
        )
    return recipients


async def close_idle(db: AsyncSession, settings: Settings, moment: datetime) -> set[int]:
    """Close open Topics without Messages for the idle time, with a line in their feed.

    Args:
        db: Database session.
        settings: Instance settings.
        moment: Now.

    Returns:
        The Users who got events, to wake after the commit.
    """
    topics = list(
        await db.scalars(
            select(Topic)
            .where(
                Topic.status == TopicStatus.Open,
                Topic.deleted_at.is_(None),
                Topic.updated_at < moment - timedelta(days=settings.idle_close_days),
            )
            .with_for_update(skip_locked=True)
        )
    )
    recipients: set[int] = set()
    for topic in topics:
        outcome = IDLE_OUTCOME.format(days=settings.idle_close_days)
        topic.last_number += 1
        # Coloqo writes the line; the opener stands as its author only to keep the row whole.
        db.add(
            Message(
                topic_id=topic.id,
                number=topic.last_number,
                kind=MessageKind.Closed,
                author_user_id=topic.created_by,
                system=True,
                body=outcome,
            )
        )
        topic.status = TopicStatus.Closed
        topic.outcome = topic.outcome or outcome
        topic.closed_at = moment
        team = list(await db.scalars(select(Member.user_id).where(Member.team_id == topic.team_id)))
        new, old = await _head(db, topic)
        closing = {
            "status": TopicStatus.Closed.value,
            "author": "Coloqo",
            "outcome": topic.outcome,
            "automatic": True,
        }
        recipients |= add_events(
            db, team, "topic_status", stored(new | closing, old | closing, topic.team_id)
        )
    return recipients


async def delete_archived(db: AsyncSession, settings: Settings, moment: datetime) -> list[Path]:
    """Delete the conversation of Topics past their archive time; keep each Topic as a card.

    Messages, files, read marks and events go; the Topic row with its title, outcome, holder
    and dates stays, so a link to it says what became of it.

    Args:
        db: Database session.
        settings: Instance settings.
        moment: Now.

    Returns:
        Files on disk to remove once the deletion is committed.
    """
    days = func.coalesce(Team.archive_days, settings.archive_days)
    topics = list(
        await db.scalars(
            select(Topic)
            .join(Team, Team.id == Topic.team_id)
            .where(
                Topic.status == TopicStatus.Closed,
                Topic.deleted_at.is_(None),
                Topic.closed_at.is_not(None),
                Topic.closed_at < moment - days * timedelta(days=1),
            )
            .with_for_update(of=Topic, skip_locked=True)
        )
    )
    gone: list[Path] = []
    for topic in topics:
        files = list(await db.scalars(select(File).where(File.topic_id == topic.id)))
        gone += [Path(settings.files_dir) / str(topic.team_id) / str(f.id) for f in files]
        await db.execute(delete(File).where(File.topic_id == topic.id))
        await db.execute(delete(Message).where(Message.topic_id == topic.id))
        await db.execute(delete(Participant).where(Participant.topic_id == topic.id))
        await db.execute(
            delete(Event).where(
                or_(
                    Event.data["topic_id"].astext == str(topic.id),
                    Event.data["legacy"]["topic_id"].astext == str(topic.id),
                )
            )
        )
        topic.deleted_at = moment
    return gone


async def tend(db: AsyncSession, settings: Settings, moment: datetime) -> set[int]:
    """Run the Topics' life cycle once: warn, close idle ones, delete archived ones.

    Args:
        db: Database session.
        settings: Instance settings.
        moment: Now.

    Returns:
        The Users who got events, to wake after the commit.

    Raises:
        OSError: A deleted Topic's file could not be removed from disk; the database change is
            committed already.
    """
    recipients = await warn_idle(db, settings, moment)
    recipients |= await close_idle(db, settings, moment)
    gone = await delete_archived(db, settings, moment)
    await db.commit()
    for path in gone:
        path.unlink(missing_ok=True)
    return recipients
