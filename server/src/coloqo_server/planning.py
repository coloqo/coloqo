"""The low level of plans: who joins a plan, with which mark (decision 0037).

Kept apart from the API modules so that tasks, when created or moved under a planned promise, and
the plans' own API both use it.
"""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from coloqo_server.models import CATEGORY, Category, Plan, PlanItem, PlanMark, Stage, Task
from coloqo_server.security import Actor
from coloqo_server.tracker import record


async def mark_for(db: AsyncSession, plan: Plan, task: Task) -> PlanMark:
    """Return the mark a task gets when it joins a plan now.

    Before approval it is planned. After, it is found when its creator named its ``source`` and
    that task is in the plan; off-plan otherwise — a ``source`` the server filled in from the held
    Topic may be unrelated urgent work, which the Team's rule is there to catch.

    Args:
        db: Database session.
        plan: The plan.
        task: The task joining.
    """
    if plan.approved_at is None:
        return PlanMark.Planned
    if task.source_given and task.source_id is not None:
        held = await db.scalar(
            select(PlanItem.task_id).where(
                PlanItem.plan_id == plan.id, PlanItem.task_id == task.source_id
            )
        )
        if held is not None:
            return PlanMark.Found
    return PlanMark.OffPlan


async def finished(db: AsyncSession, task: Task) -> bool:
    """Whether a task is finished: done, cancelled, delivered and the like.

    Args:
        db: Database session.
        task: The task.
    """
    stage = await db.get(Stage, task.stage_id)
    return stage is not None and CATEGORY[stage.kind] == Category.Finished


async def finished_before(db: AsyncSession, plan: Plan, task: Task) -> bool:
    """Whether a task was finished before the plan's period began: such work has nothing to plan.

    Work finished within the period may still join: a plan moved into Coloqo in the middle of its
    month takes in what was done since its first day (the author, 2026-11-10). A finished task with
    no moment of finishing counts as finished before.

    Args:
        db: Database session.
        plan: The plan.
        task: The task.
    """
    if not await finished(db, task):
        return False
    return task.finished_at is None or task.finished_at.date() < plan.period_start


async def join(db: AsyncSession, actor: Actor | None, plan: Plan, task: Task) -> bool:
    """Put a task into a plan with the mark it gets now; return whether it joined.

    Nothing happens for a closed plan, a task already in it, or a task finished before the plan's
    period: it has nothing to plan (the author, 2026-11-10); work finished within the period joins.
    A row another writer inserts at the same moment is found there rather than failing. The join
    is kept in the task's timeline.

    Args:
        db: Database session.
        actor: Who added it, or whose change made it join; ``None`` for Coloqo.
        plan: The plan.
        task: The task.
    """
    if plan.closed_at is not None or await finished_before(db, plan, task):
        return False
    mark = await mark_for(db, plan, task)
    inserted = await db.execute(
        insert(PlanItem)
        .values(plan_id=plan.id, task_id=task.id, mark=mark)
        .on_conflict_do_nothing(index_elements=["plan_id", "task_id"])
        .returning(PlanItem.task_id)
    )
    if inserted.scalar() is None:
        return False
    record(db, task, "plan_joined", actor, {"plan": plan.number, "name": plan.name, "mark": mark})
    return True


async def joinable_under(db: AsyncSession, plan: Plan, task: Task) -> list[Task]:
    """Return the tasks and promises under a task, at any depth, nearest first, that a plan takes:
    all but those finished before its period.

    Args:
        db: Database session.
        plan: The plan.
        task: The promise or task above.
    """
    found: list[Task] = []
    level = [task.id]
    while level:
        children = list(await db.scalars(select(Task).where(Task.parent_id.in_(level))))
        level = [c.id for c in children]
        found.extend([c for c in children if not await finished_before(db, plan, c)])
    return found


async def join_by_parent(db: AsyncSession, actor: Actor | None, task: Task) -> None:
    """Put a task into every open plan that holds one of its ancestors (decision 0037).

    Called when a task is created under, or moved under, a promise or task: work that appears
    under planned work joins the plan by itself, with the mark of the moment.

    Args:
        db: Database session.
        actor: Whose change it is.
        task: The task, with its parent set.
    """
    ancestors: list[int] = []
    above = task.parent_id
    seen: set[int] = set()
    while above is not None and above not in seen:
        seen.add(above)
        ancestors.append(above)
        above = await db.scalar(select(Task.parent_id).where(Task.id == above))
    if not ancestors:
        return
    plans = list(
        await db.scalars(
            select(Plan)
            .join(PlanItem, PlanItem.plan_id == Plan.id)
            .where(PlanItem.task_id.in_(ancestors), Plan.closed_at.is_(None))
            .distinct()
        )
    )
    for plan in plans:
        await join(db, actor, plan, task)
