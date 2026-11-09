"""The low level of plans: who joins a plan, with which mark (decision 0037).

Kept apart from the API modules so that tasks, when created or moved under a planned promise, and
the plans' own API both use it.
"""

from sqlalchemy import select
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


async def join(db: AsyncSession, actor: Actor | None, plan: Plan, task: Task) -> PlanItem | None:
    """Put a task into a plan with the mark it gets now; nothing if it is there or closed.

    The join is kept in the task's timeline.

    Args:
        db: Database session.
        actor: Who added it, or whose change made it join; ``None`` for Coloqo.
        plan: The plan.
        task: The task.
    """
    if plan.closed_at is not None:
        return None
    existing = await db.get(PlanItem, (plan.id, task.id))
    if existing is not None:
        return None
    mark = await mark_for(db, plan, task)
    item = PlanItem(plan_id=plan.id, task_id=task.id, mark=mark)
    db.add(item)
    record(db, task, "plan_joined", actor, {"plan": plan.number, "name": plan.name, "mark": mark})
    return item


async def unfinished_under(db: AsyncSession, task: Task) -> list[Task]:
    """Return the unfinished tasks and promises under a task, at any depth, nearest first.

    Args:
        db: Database session.
        task: The promise or task above.
    """
    found: list[Task] = []
    level = [task.id]
    while level:
        children = list(await db.scalars(select(Task).where(Task.parent_id.in_(level))))
        level = [c.id for c in children]
        for child in children:
            stage = await db.get(Stage, child.stage_id)
            if stage is not None and CATEGORY[stage.kind] != Category.Finished:
                found.append(child)
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
