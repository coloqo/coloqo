"""Built-in workflows and how a task finds its own (decision 0032)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from coloqo_server.models import CATEGORY, Area, Category, Stage, StageKind, TaskType, Workflow

TASK_STAGES: list[tuple[str, StageKind]] = [
    ("Backlog", StageKind.Backlog),
    ("Analysis", StageKind.Analysis),
    ("Design", StageKind.Design),
    ("Documentation", StageKind.Documentation),
    ("Agreement", StageKind.Agreement),
    ("Code", StageKind.Code),
    ("Review", StageKind.Review),
    ("Delivery", StageKind.Delivery),
    ("Done", StageKind.Done),
    ("Cancelled", StageKind.Cancelled),
]
"""The built-in task workflow: one stage per kind, in order."""

PROMISE_STAGES: list[tuple[str, StageKind]] = [
    ("Draft", StageKind.Draft),
    ("Given", StageKind.Given),
    ("Delivered", StageKind.Delivered),
    ("Not delivered", StageKind.NotDelivered),
    ("Withdrawn", StageKind.Withdrawn),
]
"""The built-in promise workflow."""

BUILT_IN = {TaskType.Task: TASK_STAGES, TaskType.Promise: PROMISE_STAGES}


async def seed(db: AsyncSession, team_id: int) -> Workflow:
    """Give a new Team the built-in workflows; return its task workflow.

    Args:
        db: Database session.
        team_id: The Team.
    """
    task_workflow: Workflow | None = None
    for type_, stages in BUILT_IN.items():
        workflow = Workflow(team_id=team_id, type=type_)
        db.add(workflow)
        await db.flush()
        for position, (name, kind) in enumerate(stages, start=1):
            db.add(Stage(workflow_id=workflow.id, name=name, kind=kind, position=position))
        if type_ == TaskType.Task:
            task_workflow = workflow
    await db.flush()
    assert task_workflow is not None
    return task_workflow


async def workflow_for(db: AsyncSession, team_id: int, type_: TaskType, area: Area) -> Workflow:
    """Return the workflow a task of this type in this Area moves by.

    A task takes its Area's workflow; a promise the Team's promise workflow (decision 0032).

    Args:
        db: Database session.
        team_id: The Team.
        type_: The task's type.
        area: The task's Area.

    Raises:
        LookupError: The Team has no workflow of this type.
    """
    if type_ == TaskType.Task and area.workflow_id is not None:
        workflow = await db.get(Workflow, area.workflow_id)
        if workflow is not None:
            return workflow
    workflow = await db.scalar(
        select(Workflow)
        .where(Workflow.team_id == team_id, Workflow.type == type_)
        .order_by(Workflow.id)
        .limit(1)
    )
    if workflow is None:
        raise LookupError(f"The Team has no {type_.value} workflow")
    return workflow


async def stages_of(db: AsyncSession, workflow_id: int) -> list[Stage]:
    """Return a workflow's current stages in order; removed ones are left out.

    Args:
        db: Database session.
        workflow_id: The workflow.
    """
    return list(
        await db.scalars(
            select(Stage)
            .where(Stage.workflow_id == workflow_id, Stage.removed_at.is_(None))
            .order_by(Stage.position)
        )
    )


def first_of(stages: list[Stage], category: Category) -> Stage:
    """Return the first stage of a category, in the workflow's order.

    Args:
        stages: A workflow's stages in order.
        category: The category.

    Raises:
        LookupError: No stage of that category is left.
    """
    for stage in stages:
        if CATEGORY[stage.kind] == category:
            return stage
    raise LookupError(f"The workflow has no stage of the category {category.value}")


def first_of_kind(stages: list[Stage], kind: StageKind) -> Stage | None:
    """Return the first stage of a kind, if the workflow has one.

    Args:
        stages: A workflow's stages in order.
        kind: The kind.
    """
    return next((stage for stage in stages if stage.kind == kind), None)
