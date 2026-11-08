"""The low level of the tracker: task rows and their timeline (decisions 0031, 0033).

Kept apart from the API modules so that Topics and tasks can both use it.
"""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from coloqo_server.models import (
    CATEGORY,
    Area,
    Category,
    Stage,
    Task,
    TaskEvent,
    TaskLink,
    TaskType,
    Team,
)
from coloqo_server.security import Actor, now


def record(
    db: AsyncSession,
    task: Task,
    kind: str,
    actor: Actor | None,
    data: dict | None = None,
    at: datetime | None = None,
) -> TaskEvent:
    """Add an entry to a task's timeline and mark the task as active.

    Args:
        db: Database session.
        task: The task.
        kind: The entry's kind, e.g. ``stage``.
        actor: Who did it; ``None`` for Coloqo itself.
        data: What the kind needs.
        at: When it happened; now when omitted.
    """
    moment = at or now()
    event = TaskEvent(
        task_id=task.id,
        kind=kind,
        author_user_id=actor.user.id if actor else None,
        author_assistant_id=actor.assistant.id if actor and actor.assistant else None,
        data=data or {},
        created_at=moment,
    )
    db.add(event)
    if kind != "move":
        task.updated_at = moment
        task.idle_noticed_at = None
    return event


async def new_task(
    db: AsyncSession,
    actor: Actor,
    team: Team,
    area: Area,
    title: str,
    type_: TaskType,
    stage: Stage,
    assignee_id: int | None,
    description: str = "",
    parent_id: int | None = None,
    source_id: int | None = None,
) -> Task:
    """Create a task with the next number of its locked Team, with its first timeline entries.

    Args:
        db: Database session, with the Team's row locked.
        actor: Who creates it.
        team: The Team.
        area: The Area.
        title: One line.
        type_: Task or promise.
        stage: Its first stage.
        assignee_id: The human it is assigned to, if any.
        description: Markdown.
        parent_id: The task or promise it belongs to.
        source_id: The task within which it is created.
    """
    team.last_task += 1
    moment = now()
    highest = await db.scalar(select(func.max(Task.rank)).where(Task.team_id == team.id))
    task = Task(
        team_id=team.id,
        number=team.last_task,
        type=type_,
        area_id=area.id,
        parent_id=parent_id,
        title=title.strip(),
        description=description,
        stage_id=stage.id,
        assignee_id=assignee_id,
        outcome="",
        rank=(highest or 0.0) + 1.0,
        source_id=source_id,
        created_by=actor.user.id,
        created_at=moment,
        updated_at=moment,
        started_at=moment if CATEGORY[stage.kind] == Category.InProgress else None,
    )
    db.add(task)
    await db.flush()
    source = await db.scalar(select(Task.number).where(Task.id == source_id)) if source_id else None
    record(db, task, "created", actor, {"source": source, "type": type_.value}, moment)
    record(db, task, "stage", actor, {"to": stage.name, "kind": stage.kind.value}, moment)
    if description:
        record(db, task, "described", actor, {"text": description}, moment)
    if assignee_id is not None:
        record(db, task, "assigned", actor, {"to": assignee_id}, moment)
    return task


async def add_link(db: AsyncSession, actor: Actor, task: Task, key: str, url: str = "") -> TaskLink:
    """Link a task to an issue of an external tracker (decision 0031).

    An address given as the key is kept as both.

    Args:
        db: Database session.
        actor: Who links it.
        task: The task.
        key: The issue's key, or its address.
        url: The issue's address.
    """
    key = key.strip()
    url = url.strip() or (key if key.startswith(("http://", "https://")) else "")
    link = TaskLink(task_id=task.id, key=key[:100], url=url[:500])
    db.add(link)
    record(db, task, "linked", actor, {"key": link.key, "url": link.url})
    return link


async def first_link(db: AsyncSession, task_id: int) -> str:
    """Return the first link of a task as a Topic's ``issue`` shows it.

    Args:
        db: Database session.
        task_id: The task.
    """
    link = await db.scalar(
        select(TaskLink).where(TaskLink.task_id == task_id).order_by(TaskLink.id).limit(1)
    )
    if link is None:
        return ""
    return link.url or link.key
