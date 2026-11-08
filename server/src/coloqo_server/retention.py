"""Quiet work: idle free Topics close, quiet tasks are noticed (decisions 0021, 0030, 0032).

Topics are no longer deleted by time (decision 0030).
"""

from datetime import datetime, timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from coloqo_server.api.teams import online
from coloqo_server.api.topics import assistants_by_id, ref, topic_head
from coloqo_server.events import add_event
from coloqo_server.models import (
    CATEGORY,
    Area,
    Assistant,
    Category,
    Message,
    MessageKind,
    Stage,
    Task,
    Team,
    Topic,
    TopicStatus,
    User,
)
from coloqo_server.settings import Settings

IDLE_OUTCOME = "Closed for inactivity: no Messages for {days} days."


async def _head(db: AsyncSession, topic: Topic, moment: datetime) -> dict:
    """Return what an event about a free Topic carries, with its holder.

    The holder's project goes with it, and whether the holder is online, so the project's
    other sessions hear about the Topic when its holder is gone (decisions 0024, 0029).

    Args:
        db: Database session.
        topic: The Topic.
        moment: Now.
    """
    team = await db.get(Team, topic.team_id)
    area = await db.get(Area, topic.area_id)
    assert team is not None
    new = topic_head(topic, team, area, None)
    holder = (await assistants_by_id(db, {topic.holder_assistant_id})).get(
        topic.holder_assistant_id or 0
    )
    row = await db.get(Assistant, topic.holder_assistant_id or 0)
    new |= {
        "holder": holder.key if holder else None,
        "holder_project": holder.project if holder else None,
        "holder_live": bool(row and online(row, moment)),
    }
    return new


async def warn_idle(db: AsyncSession, settings: Settings, moment: datetime) -> set[int]:
    """Tell the Team of free Topics about to close for inactivity, once per quiet spell.

    The event goes to the whole Team, as every event (decision 0028); a plugin shows it to the
    holder and to the holder's project's other sessions, the web shows it to nobody.

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
                Topic.task_id.is_(None),
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
        new = await _head(db, topic, moment)
        new["closes_at"] = closes_at.isoformat()
        recipients |= await add_event(db, topic.team_id, "topic_idle", new)
    return recipients


async def close_idle(db: AsyncSession, settings: Settings, moment: datetime) -> set[int]:
    """Close open free Topics without Messages for the idle time, with a line in their feed.

    A task's Topic is never closed this way: that would write a false outcome (decision 0032).

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
                Topic.task_id.is_(None),
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
        new = await _head(db, topic, moment)
        closing = {
            "status": TopicStatus.Closed.value,
            "author": "Coloqo",
            "outcome": topic.outcome,
            "automatic": True,
        }
        recipients |= await add_event(db, topic.team_id, "topic_status", new | closing)
    return recipients


async def notice_quiet_tasks(db: AsyncSession, moment: datetime) -> set[int]:
    """Tell the assignee of a task in work that has gone quiet, and again while it stays so.

    Quiet means no timeline entry and no Message in its Topic for the Team's
    ``task_idle_days``; the notice repeats every ``task_idle_repeat_days``. A task with an
    active external wait is not quiet: it waits (decision 0032). The event goes to the Team, as
    every event; the plugin shows it to the assignee's sessions.

    Args:
        db: Database session.
        moment: Now.

    Returns:
        The Users who got events, to wake after the commit.
    """
    rows = (
        await db.execute(
            select(Task, Stage, Team)
            .join(Stage, Stage.id == Task.stage_id)
            .join(Team, Team.id == Task.team_id)
            .where(
                Task.assignee_id.is_not(None),
                Task.waiting.is_(None),
                Task.updated_at < moment - Team.task_idle_days * timedelta(days=1),
                or_(
                    Task.idle_noticed_at.is_(None),
                    and_(
                        Task.idle_noticed_at
                        < moment - Team.task_idle_repeat_days * timedelta(days=1)
                    ),
                ),
            )
            .with_for_update(of=Task, skip_locked=True)
        )
    ).all()
    recipients: set[int] = set()
    for task, stage, team in rows:
        if CATEGORY[stage.kind] != Category.InProgress:
            continue
        task.idle_noticed_at = moment
        assignee = await db.get(User, task.assignee_id)
        area = await db.get(Area, task.area_id)
        recipients |= await add_event(
            db,
            team.id,
            "task_idle",
            {
                "team": team.slug,
                "task": task.number,
                "ref": ref(task.number),
                "title": task.title,
                "area": area.name if area else "",
                "stage": stage.name,
                "assignee": assignee.pseudonym if assignee else None,
                "quiet_since": task.updated_at.isoformat(),
                "days": (moment - task.updated_at).days,
            },
        )
    return recipients


async def tend(db: AsyncSession, settings: Settings, moment: datetime) -> set[int]:
    """Run the life cycle once: warn and close idle free Topics, notice quiet tasks.

    Args:
        db: Database session.
        settings: Instance settings.
        moment: Now.

    Returns:
        The Users who got events, to wake after the commit.
    """
    recipients = await warn_idle(db, settings, moment)
    recipients |= await close_idle(db, settings, moment)
    recipients |= await notice_quiet_tasks(db, moment)
    await db.commit()
    return recipients
