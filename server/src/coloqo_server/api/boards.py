"""The board and the workflow editor (decision 0032).

A board is ordered columns, each a set of stages or the condition "has an active external wait";
a task's status is the column of the main board it stands in. The first version shows one board
per Team, built from the stages' categories the first time it is asked for. The owner edits its
columns and the Team's workflows in the web.
"""

from datetime import datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from coloqo_server.api.tasks import TaskOut, assignee_by_name, task_outs
from coloqo_server.api.teams import find_area, owned, team_for
from coloqo_server.api.topics import assistants_by_id, pseudonyms, ref
from coloqo_server.models import (
    CATEGORY,
    Board,
    BoardColumn,
    Category,
    ColumnRule,
    ColumnStage,
    Message,
    Move,
    Stage,
    StageKind,
    Task,
    TaskType,
    Topic,
    Workflow,
)
from coloqo_server.security import DB, ActorDep, HumanDep, now, require_reader
from coloqo_server.tracker import record
from coloqo_server.workflows import stages_of

router = APIRouter(tags=["board"])

DONE_DAYS = 14
"""A finished task stays on the board this many days; the rest are in the list (decision 0032)."""

KINDS = {
    TaskType.Task: [
        StageKind.Backlog,
        StageKind.Analysis,
        StageKind.Design,
        StageKind.Documentation,
        StageKind.Agreement,
        StageKind.Code,
        StageKind.Review,
        StageKind.Delivery,
        StageKind.Done,
        StageKind.Cancelled,
    ],
    TaskType.Promise: [
        StageKind.Draft,
        StageKind.Given,
        StageKind.Delivered,
        StageKind.NotDelivered,
        StageKind.Withdrawn,
    ],
}
"""The kinds a workflow of each type may use."""

REQUIRED = {
    TaskType.Task: [StageKind.Backlog, StageKind.Done],
    TaskType.Promise: [StageKind.Draft, StageKind.Delivered],
}
"""The kinds a workflow must keep: tasks start in the backlog and end done (decision 0032)."""


class ColumnOut(BaseModel):
    """A column of the board.

    Attributes:
        name: The status it shows.
        rule: ``stages``, or ``waiting`` for tasks with an active external wait.
        stages: Names of its stages, for a column by stages.
    """

    name: str
    rule: ColumnRule
    stages: list[str]


class Promise(BaseModel):
    """The promise a task works towards.

    Attributes:
        number: Its number.
        title: Its title.
    """

    number: int
    title: str


class Card(TaskOut):
    """A task on the board.

    Attributes:
        column: The index of the column it stands in.
        promise: The nearest promise above it.
        move: Whose move it is: ``assistant``, ``human`` (its human), ``person`` (another
            person of the Team), ``external``; ``None`` when nothing tells (decision 0033).
        move_who: Who: the Assistant's name, a pseudonym, or what is awaited.
        move_since: Since when, if known.
    """

    column: int
    promise: Promise | None
    move: Literal["assistant", "human", "person", "external"] | None
    move_who: str | None
    move_since: datetime | None


class BoardOut(BaseModel):
    """The board with the tasks on it.

    Attributes:
        name: The board's name.
        columns: Its columns in order.
        cards: The tasks, highest first within a column; promises are not on the board.
    """

    name: str
    columns: list[ColumnOut]
    cards: list[Card]


class ColumnIn(BaseModel):
    """A column as the owner sets it.

    Attributes:
        name: The status it shows.
        rule: ``stages`` or ``waiting``.
        stages: Names of its stages, for a column by stages.
    """

    name: str = Field(min_length=1, max_length=60)
    rule: ColumnRule = ColumnRule.Stages
    stages: list[str] = Field(default_factory=list, max_length=50)


class BoardIn(BaseModel):
    """The board's columns as the owner sets them.

    Attributes:
        columns: The columns in order; every stage of the Team's task workflows stands in
            exactly one column by stages, and there is at most one waiting column.
    """

    columns: list[ColumnIn] = Field(min_length=1, max_length=20)


class StageIn(BaseModel):
    """A stage in the edited workflow.

    Attributes:
        name: Its name, unique in the workflow.
        kind: Its fixed kind; an existing stage keeps its kind (remove it and add another).
        was: The current name of the existing stage it is; ``None`` for a new stage.
    """

    name: str = Field(min_length=1, max_length=60)
    kind: StageKind
    was: str | None = None


class WorkflowIn(BaseModel):
    """A workflow as the owner edits it.

    Attributes:
        stages: Its stages in order.
        moves: For each removed stage that has tasks, the new name of the stage to move them to.
    """

    stages: list[StageIn] = Field(min_length=1, max_length=40)
    moves: dict[str, str] = Field(default_factory=dict)


async def task_stages(db: AsyncSession, team_id: int) -> list[Stage]:
    """Return the current stages of the Team's task workflows.

    Args:
        db: Database session.
        team_id: The Team.
    """
    return list(
        await db.scalars(
            select(Stage)
            .join(Workflow, Workflow.id == Stage.workflow_id)
            .where(
                Workflow.team_id == team_id,
                Workflow.type == TaskType.Task,
                Stage.removed_at.is_(None),
            )
            .order_by(Workflow.id, Stage.position)
        )
    )


async def main_board(db: AsyncSession, team_id: int) -> Board:
    """Return the Team's main board, built and brought in line with its stages.

    Built from the categories: "To do", "In progress", "Done". A stage the board does not show
    yet, such as one added in the workflow editor, joins the first column that shows a stage of
    its category, or the last column by stages.

    Args:
        db: Database session.
        team_id: The Team.
    """
    board = await db.scalar(
        select(Board).where(Board.team_id == team_id, Board.main.is_(True)).limit(1)
    )
    stages = await task_stages(db, team_id)
    if board is None:
        board = Board(team_id=team_id, name="Board", main=True)
        db.add(board)
        await db.flush()
        for position, (name, category) in enumerate(
            (
                ("To do", Category.ToDo),
                ("In progress", Category.InProgress),
                ("Done", Category.Finished),
            ),
            start=1,
        ):
            column = BoardColumn(
                board_id=board.id, name=name, position=position, rule=ColumnRule.Stages
            )
            db.add(column)
            await db.flush()
            for stage in stages:
                if CATEGORY[stage.kind] == category:
                    db.add(ColumnStage(column_id=column.id, stage_id=stage.id, board_id=board.id))
        await db.flush()
        return board
    shown = set(
        await db.scalars(select(ColumnStage.stage_id).where(ColumnStage.board_id == board.id))
    )
    missing = [stage for stage in stages if stage.id not in shown]
    if missing:
        columns = await columns_of(db, board)
        by_stages = [column for column, _ in columns if column.rule == ColumnRule.Stages]
        for stage in missing:
            home = next(
                (
                    column
                    for column, held in columns
                    if column.rule == ColumnRule.Stages
                    and any(CATEGORY[s.kind] == CATEGORY[stage.kind] for s in held)
                ),
                by_stages[-1] if by_stages else None,
            )
            if home is not None:
                db.add(ColumnStage(column_id=home.id, stage_id=stage.id, board_id=board.id))
        await db.flush()
    return board


async def columns_of(db: AsyncSession, board: Board) -> list[tuple[BoardColumn, list[Stage]]]:
    """Return a board's columns in order with their current stages.

    Args:
        db: Database session.
        board: The board.
    """
    columns = list(
        await db.scalars(
            select(BoardColumn)
            .where(BoardColumn.board_id == board.id)
            .order_by(BoardColumn.position)
        )
    )
    held: dict[int, list[Stage]] = {column.id: [] for column in columns}
    rows = await db.execute(
        select(ColumnStage.column_id, Stage)
        .join(Stage, Stage.id == ColumnStage.stage_id)
        .where(ColumnStage.board_id == board.id, Stage.removed_at.is_(None))
        .order_by(Stage.position)
    )
    for column_id, stage in rows:
        held[column_id].append(stage)
    return [(column, held[column.id]) for column in columns]


async def moves(
    db: AsyncSession, tasks: list[Task]
) -> dict[int, tuple[str, str | None, datetime | None]]:
    """Return whose move it is for each task (decision 0033).

    An external wait is the move of what is awaited. Otherwise the newest Message of its Topic
    addressed to another person who has not written since makes it theirs. Otherwise the session
    holding its Topic tells: after its last interval of the Assistant's move it is the human's,
    after one of the human's it is the Assistant's.

    Args:
        db: Database session.
        tasks: The tasks.
    """
    result: dict[int, tuple[str, str | None, datetime | None]] = {}
    topics = {
        topic.task_id: topic
        for topic in await db.scalars(select(Topic).where(Topic.task_id.in_([t.id for t in tasks])))
    }
    holders = await assistants_by_id(db, {t.holder_assistant_id for t in topics.values()})
    names = await pseudonyms(db, {t.assignee_id for t in tasks})
    for task in tasks:
        if task.waiting:
            result[task.id] = ("external", task.waiting, None)
            continue
        topic = topics.get(task.id)
        if topic is None:
            continue
        asked = await db.scalar(
            select(Message)
            .where(
                Message.topic_id == topic.id,
                Message.to_user_id.is_not(None),
                Message.to_user_id != task.assignee_id,
            )
            .order_by(Message.number.desc())
            .limit(1)
        )
        if asked is not None:
            answered = await db.scalar(
                select(Message.id)
                .where(
                    Message.topic_id == topic.id,
                    Message.author_user_id == asked.to_user_id,
                    Message.number > asked.number,
                )
                .limit(1)
            )
            if answered is None:
                person = (await pseudonyms(db, {asked.to_user_id})).get(asked.to_user_id or 0)
                result[task.id] = ("person", person, asked.created_at)
                continue
        if topic.holder_assistant_id is None:
            continue
        last = await db.scalar(
            select(Move)
            .where(Move.assistant_id == topic.holder_assistant_id)
            .order_by(Move.ended_at.desc())
            .limit(1)
        )
        if last is None:
            continue
        holder = holders.get(topic.holder_assistant_id)
        if last.move == "assistant":
            result[task.id] = ("human", names.get(task.assignee_id or 0), last.ended_at)
        else:
            result[task.id] = ("assistant", holder.name if holder else None, last.ended_at)
    return result


def promise_of(task: Task, by_id: dict[int, Task]) -> Task | None:
    """Return the nearest promise above a task.

    Args:
        task: The task.
        by_id: The Team's tasks by id.
    """
    parent = by_id.get(task.parent_id or 0)
    while parent is not None:
        if parent.type == TaskType.Promise:
            return parent
        parent = by_id.get(parent.parent_id or 0)
    return None


def under(task: Task, ancestor_id: int, by_id: dict[int, Task]) -> bool:
    """Whether a task stands anywhere below a task or promise.

    Args:
        task: The task.
        ancestor_id: The task or promise above.
        by_id: The Team's tasks by id.
    """
    parent = by_id.get(task.parent_id or 0)
    while parent is not None:
        if parent.id == ancestor_id:
            return True
        parent = by_id.get(parent.parent_id or 0)
    return False


@router.get("/team/{team}/board")
async def read_board(
    team: str,
    actor: ActorDep,
    db: DB,
    area: Annotated[str | None, Query()] = None,
    assignee: Annotated[str | None, Query()] = None,
    promise: Annotated[int | None, Query()] = None,
) -> BoardOut:
    """Return the Team's board with its tasks and subtasks; promises are not on it.

    A task stands in the waiting column while it waits, if the board has one, otherwise in the
    column of its stage. A finished task stays 14 days. Filters narrow the view; a link keeps
    them.

    Args:
        team: The Team's slug.
        actor: The caller.
        db: Database session.
        area: Only this Area, by slug.
        assignee: Only this person's; ``-`` for unassigned.
        promise: Only what stands below this promise or goal, by number.

    Raises:
        HTTPException: 404 when the caller is not in the Team, or for an unknown Area or
            promise; 422 for an unknown pseudonym.
    """
    require_reader(actor)
    found, _ = await team_for(db, team, actor.user.id)
    board = await main_board(db, found.id)
    columns = await columns_of(db, board)
    await db.commit()
    tasks = list(
        await db.scalars(
            select(Task).where(Task.team_id == found.id).order_by(Task.rank, Task.number)
        )
    )
    by_id = {task.id: task for task in tasks}
    shown = [
        task
        for task in tasks
        if task.type == TaskType.Task
        and (task.finished_at is None or task.finished_at > now() - timedelta(days=DONE_DAYS))
    ]
    if area is not None:
        row = await find_area(db, found.id, area)
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No such Area")
        shown = [task for task in shown if task.area_id == row.id]
    if assignee == "-":
        shown = [task for task in shown if task.assignee_id is None]
    elif assignee is not None:
        user = await assignee_by_name(db, found.id, assignee)
        shown = [task for task in shown if task.assignee_id == user.id]
    if promise is not None:
        top = next((t for t in tasks if t.number == promise), None)
        if top is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"No such promise {ref(promise)}")
        shown = [task for task in shown if under(task, top.id, by_id)]
    stage_column = {
        stage.id: index
        for index, (column, held) in enumerate(columns)
        if column.rule == ColumnRule.Stages
        for stage in held
    }
    waiting = next(
        (index for index, (column, _) in enumerate(columns) if column.rule == ColumnRule.Waiting),
        None,
    )
    outs = {out.number: out for out in await task_outs(db, shown)}
    whose = await moves(db, shown)
    cards = []
    for task in shown:
        column = (
            waiting if task.waiting and waiting is not None else stage_column.get(task.stage_id)
        )
        if column is None:
            continue
        above = promise_of(task, by_id)
        move = whose.get(task.id)
        cards.append(
            Card(
                **outs[task.number].model_dump(),
                column=column,
                promise=Promise(number=above.number, title=above.title) if above else None,
                move=move[0] if move else None,  # type: ignore[arg-type]
                move_who=move[1] if move else None,
                move_since=move[2] if move else None,
            )
        )
    return BoardOut(
        name=board.name,
        columns=[
            ColumnOut(name=column.name, rule=column.rule, stages=[s.name for s in held])
            for column, held in columns
        ],
        cards=cards,
    )


@router.put("/team/{team}/board")
async def set_board(team: str, body: BoardIn, actor: HumanDep, db: DB) -> list[ColumnOut]:
    """Set the board's columns: the owner groups the stages into statuses (decision 0032).

    Args:
        team: The Team's slug.
        body: The columns.
        actor: The logged-in owner.
        db: Database session.

    Raises:
        HTTPException: 404 when the caller is not in the Team; 403 when not its owner; 422 when
            a stage is unknown, shown twice or not shown, a waiting column names stages, or
            there is more than one waiting column.
    """
    found = await owned(db, team, actor.user.id)
    board = await main_board(db, found.id)
    stages = {stage.name.lower(): stage for stage in await task_stages(db, found.id)}
    seen: set[int] = set()
    waiting = 0
    for column in body.columns:
        if column.rule == ColumnRule.Waiting:
            waiting += 1
            if column.stages:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    f"The waiting column «{column.name}» shows tasks by their wait, not by stages",
                )
            continue
        for name in column.stages:
            stage = stages.get(name.strip().lower())
            if stage is None:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"No stage {name!r}")
            if stage.id in seen:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT, f"The stage {stage.name} is shown twice"
                )
            seen.add(stage.id)
    if waiting > 1:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "One waiting column at most")
    left = [stage.name for stage in stages.values() if stage.id not in seen]
    if left:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"Every stage stands in one column; not shown: {', '.join(left)}",
        )
    await db.execute(delete(BoardColumn).where(BoardColumn.board_id == board.id))
    for position, column in enumerate(body.columns, start=1):
        row = BoardColumn(
            board_id=board.id, name=column.name.strip(), position=position, rule=column.rule
        )
        db.add(row)
        await db.flush()
        for name in column.stages:
            stage = stages[name.strip().lower()]
            db.add(ColumnStage(column_id=row.id, stage_id=stage.id, board_id=board.id))
    await db.commit()
    return [
        ColumnOut(name=column.name, rule=column.rule, stages=[s.name for s in held])
        for column, held in await columns_of(db, board)
    ]


@router.put("/team/{team}/workflow/{type_}")
async def edit_workflow(
    team: str, type_: TaskType, body: WorkflowIn, actor: HumanDep, db: DB
) -> list[str]:
    """Edit the Team's workflow of a type: rename, reorder, add and remove stages (0032).

    An existing stage keeps its kind; to change a kind, remove the stage and add another. A
    removed stage stays in history under its name; its tasks move to the stage named in
    ``moves``, each with a timeline entry. The kinds the type needs stay: the backlog and done
    for tasks, a draft and delivered for promises.

    Args:
        team: The Team's slug.
        type_: ``task`` or ``promise``.
        body: The stages in order and where to move the tasks of removed ones.
        actor: The logged-in owner.
        db: Database session.

    Raises:
        HTTPException: 404 when the caller is not in the Team; 403 when not its owner; 422 for
            a repeated name, a kind of another type, a changed kind, a missing required kind,
            an unknown stage, or a removed stage with tasks and no stage to move them to.
    """
    found = await owned(db, team, actor.user.id)
    workflow = await db.scalar(
        select(Workflow)
        .where(Workflow.team_id == found.id, Workflow.type == type_)
        .order_by(Workflow.id)
        .limit(1)
    )
    if workflow is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"The Team has no {type_.value} workflow")
    current = {stage.name: stage for stage in await stages_of(db, workflow.id)}
    names = [stage.name.strip() for stage in body.stages]
    if len({name.lower() for name in names}) != len(names):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Stage names repeat")
    for stage in body.stages:
        if stage.kind not in KINDS[type_]:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"A {type_.value} workflow has no kind {stage.kind.value}",
            )
        if stage.was is not None:
            old = current.get(stage.was)
            if old is None:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT, f"No stage {stage.was!r} to keep"
                )
            if old.kind != stage.kind:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    f"{old.name} keeps its kind {old.kind.value}; remove it and add another",
                )
    missing = [k.value for k in REQUIRED[type_] if k not in {s.kind for s in body.stages}]
    if missing:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"The workflow needs {', '.join(missing)}"
        )
    kept = {stage.was for stage in body.stages if stage.was is not None}
    removed = [stage for name, stage in current.items() if name not in kept]
    moment = now()
    # Free the names first: a removed or renamed stage may give its name to another.
    for stage in current.values():
        stage.name = f"~{stage.id}"
    await db.flush()
    by_name: dict[str, Stage] = {}
    for position, item in enumerate(body.stages, start=1):
        if item.was is not None:
            stage = current[item.was]
            stage.name, stage.position = item.name.strip(), position
        else:
            stage = Stage(
                workflow_id=workflow.id, name=item.name.strip(), kind=item.kind, position=position
            )
            db.add(stage)
        by_name[item.name.strip().lower()] = stage
    await db.flush()
    for stage in removed:
        old_name = next(name for name, s in current.items() if s is stage)
        stage.removed_at = moment
        stage.name = f"{old_name[:40]} (removed {stage.id})"
        stage.position = 0
        tasks = list(await db.scalars(select(Task).where(Task.stage_id == stage.id)))
        if not tasks:
            continue
        target = by_name.get(body.moves.get(old_name, "").strip().lower())
        if target is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"{old_name} has tasks: name the stage to move them to in moves",
            )
        for task in tasks:
            task.stage_id = target.id
            record(
                db,
                task,
                "stage",
                actor,
                {"from": old_name, "to": target.name, "kind": target.kind.value, "workflow": True},
            )
    await db.commit()
    return [stage.name for stage in await stages_of(db, workflow.id)]
