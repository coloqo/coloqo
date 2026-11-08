"""Tasks: the tracker's API (decisions 0031, 0032, 0033).

A task is ``T-<number>`` in its Team. Only the assignee's Assistant moves and closes it; a human
in the web plans: assigns and orders. Planning needs the tracker on; taking, moving and closing
work without it. Every change goes to the task's timeline.
"""

from datetime import date, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from coloqo_server.api.teams import find_area, team_for
from coloqo_server.api.topics import (
    FEED_LIMIT,
    TopicDetail,
    assistants_by_id,
    feed,
    hold,
    post,
    pseudonyms,
    ref,
    status_event,
    topic_detail,
    topic_head,
)
from coloqo_server.events import add_event
from coloqo_server.models import (
    CATEGORY,
    Area,
    Category,
    Member,
    MessageKind,
    Move,
    Stage,
    StageKind,
    Task,
    TaskEvent,
    TaskLink,
    TaskType,
    Team,
    Topic,
    TopicStatus,
    User,
    Workflow,
)
from coloqo_server.security import DB, Actor, ActorDep, now, require_reader, require_writer
from coloqo_server.tracker import add_link, first_link, new_task, record
from coloqo_server.workflows import first_of, first_of_kind, stages_of, start_of, workflow_for

router = APIRouter(tags=["tasks"])

MOVE_MAX = timedelta(hours=12)
"""The longest move interval accepted; a longer one is a session left open overnight."""


class LinkOut(BaseModel):
    """A link to an issue of an external tracker.

    Attributes:
        key: The issue's key.
        url: Its address, if known.
    """

    key: str
    url: str


class Progress(BaseModel):
    """What a promise holds, done against all.

    Attributes:
        done: Done or delivered.
        total: All but the cancelled and withdrawn.
    """

    done: int
    total: int


class TaskOut(BaseModel):
    """A task in a list.

    Attributes:
        team: The Team's slug.
        number: Its number in the Team.
        ref: Short reference, ``T-<number>``.
        type: ``task`` or ``promise``.
        area: The Area's slug.
        area_name: The Area's name.
        title: One line.
        stage: Its stage's name.
        stage_kind: That stage's fixed kind.
        category: ``to_do``, ``in_progress`` or ``finished``.
        assignee: Pseudonym of the human it is assigned to.
        waiting: What it waits for, while it waits.
        outcome: How it ended.
        parent: The number of the task or promise it belongs to.
        source: The number of the task within which it was created.
        links: Its links to external issues.
        has_topic: It has a Topic.
        holder: Name of the Assistant holding its Topic.
        holder_key: Its key.
        created_by: Pseudonym of whoever created it.
        rank: Its place within its status: smaller stands higher.
        period_start: A promise's first day.
        period_end: A promise's last day.
        progress: For a promise, what it holds: done against all, the cancelled and withdrawn
            left out (decision 0031).
        created_at: Creation time.
        updated_at: Time of its newest activity.
        started_at: Its first move into work.
        finished_at: When it was finished.
    """

    team: str
    number: int
    ref: str
    type: TaskType
    area: str
    area_name: str
    title: str
    stage: str
    stage_kind: StageKind
    category: Category
    assignee: str | None
    waiting: str | None
    outcome: str
    parent: int | None
    source: int | None
    links: list[LinkOut]
    has_topic: bool
    holder: str | None
    holder_key: str | None
    created_by: str | None
    rank: float
    period_start: date | None = None
    period_end: date | None = None
    progress: Progress | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class TimelineOut(BaseModel):
    """An entry of a task's timeline (decision 0033).

    Attributes:
        kind: ``created``, ``stage``, ``skipped``, ``assigned``, ``waiting``, ``resumed``,
            ``described``, ``linked``, ``closed``, ``move``, ...
        author: Pseudonym of the human on whose behalf it happened; ``None`` for Coloqo.
        assistant: Name of the Assistant that did it, if any.
        data: What the kind carries.
        created_at: When it happened.
    """

    kind: str
    author: str | None
    assistant: str | None
    data: dict
    created_at: datetime


class TaskDetail(TaskOut):
    """A task with its description, timeline and Topic.

    Attributes:
        description: Markdown.
        timeline: Its timeline, oldest first.
        topic: Its Topic with some Messages, if it has one.
    """

    description: str
    timeline: list[TimelineOut]
    topic: TopicDetail | None


class StageOut(BaseModel):
    """A stage of a workflow.

    Attributes:
        name: Its name.
        kind: Its fixed kind.
        category: Its kind's category.
    """

    name: str
    kind: StageKind
    category: Category


class WorkflowOut(BaseModel):
    """A workflow with its stages in order.

    Attributes:
        type: The type of task it serves.
        areas: Slugs of the Areas whose tasks move by it; empty for the promise workflow.
        stages: Its stages.
    """

    type: TaskType
    areas: list[str]
    stages: list[StageOut]


class TaskIn(BaseModel):
    """A new task in the backlog: planning, so the tracker must be on (decision 0032).

    Attributes:
        area: The Area's slug.
        title: One line.
        description: Markdown.
        type: ``task`` or ``promise``.
        parent: The number of the task or promise it belongs to.
        source: The number of the task within which it is created; by default the task whose
            Topic the calling Assistant holds, if exactly one.
        assignee: Pseudonym of the human to assign it to.
        links: Keys or addresses of external issues.
        period_start: A promise's first day.
        period_end: A promise's last day.
    """

    area: str = Field(min_length=1, max_length=40)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=50_000)
    type: TaskType = TaskType.Task
    period_start: date | None = None
    period_end: date | None = None
    parent: int | None = None
    source: int | None = None
    assignee: str | None = None
    links: list[str] = Field(default_factory=list, max_length=20)


class TakeIn(BaseModel):
    """Taking a task into work (decision 0032).

    Attributes:
        body: The first Message of its Topic, when the Topic is opened now.
        reassign: Take a task assigned to another human, as an explicit reassignment.
        with_human: The Assistant's human asked for the first Message or saw its text.
    """

    body: str | None = Field(default=None, max_length=50_000)
    reassign: bool = False
    with_human: bool = False


class StageIn(BaseModel):
    """Moving a task to another stage of work.

    Attributes:
        stage: The stage's name, any case.
        skip: Stages passed at once, by name, each with its reason ("no documentation
            changes"); the timeline keeps them.
        comment: A line about the move.
    """

    stage: str = Field(min_length=1, max_length=60)
    skip: dict[str, str] = Field(default_factory=dict, max_length=20)
    comment: str = Field(default="", max_length=300)


class WaitIn(BaseModel):
    """An external wait over the task's stage (decision 0033).

    Attributes:
        what: Whom or what the task waits for.
    """

    what: str = Field(min_length=1, max_length=300)


class CloseIn(BaseModel):
    """Closing a task or a promise.

    Attributes:
        outcome: A line or two, with the MR or issue links.
        cancelled: Closed without a result: a task cancelled, a promise withdrawn.
        missed: A promise whose period ended without the delivery: not delivered (0032).
    """

    outcome: str = Field(min_length=1, max_length=5000)
    cancelled: bool = False
    missed: bool = False


class TaskPatch(BaseModel):
    """Editing a task; every description is kept in the timeline.

    Attributes:
        title: A new title.
        description: A new description.
        area: A new Area, by slug; the number stays.
        period_start: A promise's first day.
        period_end: A promise's last day.
    """

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=50_000)
    area: str | None = Field(default=None, min_length=1, max_length=40)
    period_start: date | None = None
    period_end: date | None = None


class LinkIn(BaseModel):
    """A link to an external issue.

    Attributes:
        key: The issue's key or address.
        url: Its address.
    """

    key: str = Field(min_length=1, max_length=500)
    url: str = Field(default="", max_length=500)


class AssignIn(BaseModel):
    """Assigning a task: planning (decision 0031).

    Attributes:
        assignee: Pseudonym of a human of the Team; ``None`` to unassign.
    """

    assignee: str | None = None


class OrderIn(BaseModel):
    """Placing a task within its status: higher matters more (decision 0031).

    Attributes:
        before: The number of the task it goes right above.
        after: The number of the task it goes right below.
    """

    before: int | None = None
    after: int | None = None


class MoveIn(BaseModel):
    """An interval of whose move it was, between an Assistant and its human (decision 0033).

    Attributes:
        move: ``assistant`` from a human's prompt to the Assistant's stop, ``human`` from the
            stop to the next prompt.
        start: When it began.
        end: When it ended.
    """

    move: Literal["assistant", "human"]
    start: datetime
    end: datetime


class MovesIn(BaseModel):
    """Move intervals of the calling session.

    Attributes:
        intervals: The intervals, any order.
    """

    intervals: list[MoveIn] = Field(max_length=500)


class MovesOut(BaseModel):
    """What was recorded.

    Attributes:
        recorded: Intervals kept; a repeated or a malformed one is not.
    """

    recorded: int


async def task_outs(db: AsyncSession, tasks: list[Task]) -> list[TaskOut]:
    """Build the list view of tasks.

    Args:
        db: Database session.
        tasks: The tasks.
    """
    if not tasks:
        return []
    ids = [task.id for task in tasks]
    teams = {
        t.id: t
        for t in await db.scalars(select(Team).where(Team.id.in_({x.team_id for x in tasks})))
    }
    areas = {
        a.id: a
        for a in await db.scalars(select(Area).where(Area.id.in_({x.area_id for x in tasks})))
    }
    stages = {
        s.id: s
        for s in await db.scalars(select(Stage).where(Stage.id.in_({x.stage_id for x in tasks})))
    }
    related = ({x.parent_id for x in tasks} | {x.source_id for x in tasks}) - {None}
    numbers: dict[int, int] = {
        task_id: number
        for task_id, number in await db.execute(
            select(Task.id, Task.number).where(Task.id.in_(related))
        )
    }
    links: dict[int, list[LinkOut]] = {}
    for link in await db.scalars(
        select(TaskLink).where(TaskLink.task_id.in_(ids)).order_by(TaskLink.id)
    ):
        links.setdefault(link.task_id, []).append(LinkOut(key=link.key, url=link.url))
    topics = {t.task_id: t for t in await db.scalars(select(Topic).where(Topic.task_id.in_(ids)))}
    holders = await assistants_by_id(db, {t.holder_assistant_id for t in topics.values()})
    progress: dict[int, Progress] = {}
    promises = [x.id for x in tasks if x.type == TaskType.Promise]
    if promises:
        counts: dict[int, list[int]] = {pid: [0, 0] for pid in promises}
        rows = await db.execute(
            select(Task.parent_id, Stage.kind)
            .join(Stage, Stage.id == Task.stage_id)
            .where(Task.parent_id.in_(promises))
        )
        for parent_id, kind in rows:
            if kind in (StageKind.Cancelled, StageKind.Withdrawn):
                continue
            counts[parent_id][1] += 1
            if kind in (StageKind.Done, StageKind.Delivered):
                counts[parent_id][0] += 1
        progress = {pid: Progress(done=d, total=t) for pid, (d, t) in counts.items()}
    users = await pseudonyms(db, {x.assignee_id for x in tasks} | {x.created_by for x in tasks})
    result = []
    for task in tasks:
        stage = stages[task.stage_id]
        area = areas.get(task.area_id)
        topic = topics.get(task.id)
        holder = holders.get(topic.holder_assistant_id or 0) if topic else None
        result.append(
            TaskOut(
                team=teams[task.team_id].slug,
                number=task.number,
                ref=ref(task.number),
                type=task.type,
                area=area.slug if area else "",
                area_name=area.name if area else "",
                title=task.title,
                stage=stage.name,
                stage_kind=stage.kind,
                category=CATEGORY[stage.kind],
                assignee=users.get(task.assignee_id) if task.assignee_id else None,
                waiting=task.waiting,
                outcome=task.outcome,
                parent=numbers.get(task.parent_id) if task.parent_id else None,
                source=numbers.get(task.source_id) if task.source_id else None,
                links=links.get(task.id, []),
                has_topic=topic is not None,
                holder=holder.name if holder else None,
                holder_key=holder.key if holder else None,
                created_by=users.get(task.created_by),
                rank=task.rank,
                period_start=task.period_start,
                period_end=task.period_end,
                progress=progress.get(task.id),
                created_at=task.created_at,
                updated_at=task.updated_at,
                started_at=task.started_at,
                finished_at=task.finished_at,
            )
        )
    return result


async def timeline(db: AsyncSession, task: Task) -> list[TimelineOut]:
    """Return a task's timeline, oldest first.

    Args:
        db: Database session.
        task: The task.
    """
    events = list(
        await db.scalars(
            select(TaskEvent)
            .where(TaskEvent.task_id == task.id)
            .order_by(TaskEvent.created_at, TaskEvent.id)
        )
    )
    users = await pseudonyms(db, {e.author_user_id for e in events})
    assistants = await assistants_by_id(db, {e.author_assistant_id for e in events})
    return [
        TimelineOut(
            kind=e.kind,
            author=users.get(e.author_user_id) if e.author_user_id else None,
            assistant=a.name if (a := assistants.get(e.author_assistant_id or 0)) else None,
            data=e.data,
            created_at=e.created_at,
        )
        for e in events
    ]


async def task_for(
    db: AsyncSession, team: str, number: int, actor: Actor, write: bool = False
) -> tuple[Task, Team]:
    """Return a task by its Team's slug and number, locked when it is to be changed.

    Args:
        db: Database session.
        team: The Team's slug, current or former.
        number: The task's number.
        actor: The caller.
        write: The caller is about to change it: an Assistant must be linked to its Team.

    Raises:
        HTTPException: 404 when there is no such task in the caller's Teams; 403 when the
            caller may not write there.
    """
    require_reader(actor)
    found, _ = await team_for(db, team, actor.user.id)
    query = select(Task).where(Task.team_id == found.id, Task.number == number)
    task = await db.scalar(query.with_for_update() if write else query)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No such task {found.slug}/{ref(number)}")
    if write:
        await require_writer(db, actor, found.id)
    return task, found


def need_tracker(team: Team) -> None:
    """Refuse planning in a Team without the tracker (decision 0032).

    Args:
        team: The Team.

    Raises:
        HTTPException: 409 ``no_tracker``.
    """
    if not team.tracker:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "code": "no_tracker",
                "message": f"«{team.name}» has no tracker: no backlog and no assigning. A Team "
                "owner turns the tracker on in the Team's settings; until then mention found "
                "work in the Topic.",
            },
        )


def need_assignees_assistant(actor: Actor, task: Task, label: str, topic: Topic | None) -> None:
    """Refuse anyone but an Assistant of the task's assignee (decision 0032).

    The Assistant holding the task's Topic may close it too, as plugins older than the tracker
    do through the Topic.

    Args:
        actor: The caller.
        task: The task.
        label: How the caller names the task.
        topic: The task's Topic, when the holder is allowed.

    Raises:
        HTTPException: 403 for a human; 409 ``not_assignee`` for another Assistant.
    """
    if actor.assistant is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"Only the assignee's Assistant moves {label}: ask yours (decision 0032)",
        )
    holder = topic is not None and topic.holder_assistant_id == actor.assistant.id
    if task.assignee_id != actor.user.id and not holder:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "code": "not_assignee",
                "message": f"{label} is not assigned to your user; write in its Topic instead, "
                "or take it with reassign=true if your user takes it over.",
            },
        )


async def task_event(
    db: AsyncSession, actor: Actor | None, task: Task, change: str, **more: object
) -> set[int]:
    """Tell the Team that a task changed.

    Args:
        db: Database session.
        actor: Who changed it; ``None`` for Coloqo.
        task: The task, in its new state.
        change: ``created``, ``stage``, ``assigned``, ``waiting``, ``resumed``, ``closed``, ...
        more: More data.

    Returns:
        The Users who got the event, to wake after the commit.
    """
    team = await db.get(Team, task.team_id)
    area = await db.get(Area, task.area_id)
    stage = await db.get(Stage, task.stage_id)
    assert team is not None and stage is not None
    users = await pseudonyms(db, {task.assignee_id})
    author = None
    if actor is not None and actor.assistant is not None:
        author = (await assistants_by_id(db, {actor.assistant.id})).get(actor.assistant.id)
    data = {
        "team": team.slug,
        "topic_kind": "task",
        "task": task.number,
        "ref": ref(task.number),
        "title": task.title,
        "area": area.name if area else "",
        "event": change,
        "stage": stage.name,
        "stage_kind": stage.kind.value,
        "assignee": users.get(task.assignee_id or 0),
        "author": author.name if author else (actor.user.pseudonym if actor else "Coloqo"),
        "author_assistant": author.key if author else None,
    } | more
    return await add_event(db, team.id, "task", data)


async def stage_by_name(db: AsyncSession, task: Task, name: str, label: str) -> Stage:
    """Return a stage of the task's workflow by its name, any case.

    Args:
        db: Database session.
        task: The task.
        name: The stage's name.
        label: How the caller names the task.

    Raises:
        HTTPException: 422 when the workflow has no such stage; the detail lists them.
    """
    current = await db.get(Stage, task.stage_id)
    assert current is not None
    stages = await stages_of(db, current.workflow_id)
    for stage in stages:
        if stage.name.lower() == name.strip().lower():
            return stage
    raise HTTPException(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        f"{label} has no stage {name!r}; its stages: {', '.join(s.name for s in stages)}",
    )


async def topic_of(db: AsyncSession, task: Task, lock: bool = False) -> Topic | None:
    """Return a task's Topic, if it has one.

    Args:
        db: Database session.
        task: The task.
        lock: Lock its row, to number a new Message.
    """
    query = select(Topic).where(Topic.task_id == task.id)
    return await db.scalar(query.with_for_update() if lock else query)


async def move_to(
    db: AsyncSession, actor: Actor, task: Task, stage: Stage, line: str, data: dict
) -> set[int]:
    """Move a locked task to a stage: timeline, Topic line, event.

    Args:
        db: Database session.
        actor: Who moves it.
        task: The task.
        stage: The new stage.
        line: The service line its Topic shows.
        data: More timeline data.

    Returns:
        The Users who got events, to wake after the commit.
    """
    former = await db.get(Stage, task.stage_id)
    assert former is not None
    task.stage_id = stage.id
    if CATEGORY[stage.kind] == Category.InProgress and task.started_at is None:
        task.started_at = now()
    record(
        db,
        task,
        "stage",
        actor,
        {"from": former.name, "to": stage.name, "kind": stage.kind.value} | data,
    )
    recipients: set[int] = set()
    topic = await topic_of(db, task, lock=True)
    if topic is not None:
        _, recipients = await post(db, actor, topic, line, MessageKind.Stage, None, [])
    return recipients | await task_event(db, actor, task, "stage")


async def close_task(
    db: AsyncSession,
    actor: Actor,
    task: Task,
    outcome: str,
    cancelled: bool,
    label: str,
    topic: Topic | None = None,
    missed: bool = False,
) -> set[int]:
    """Finish a locked task as done or cancelled, a promise as delivered, not delivered or
    withdrawn; its Topic closes with it (decision 0032).

    Args:
        db: Database session.
        actor: The assignee's Assistant, or the holder of its Topic.
        task: The task.
        outcome: A line or two with the links.
        cancelled: Closed without a result.
        label: How the caller names the task.
        topic: Its Topic, already locked, if the caller came through it.
        missed: A promise not delivered in its period.

    Returns:
        The Users who got events, to wake after the commit.

    Raises:
        HTTPException: 403 for a human; 409 ``not_assignee`` for another Assistant, or
            ``finished`` when it is finished already; 422 without an outcome or without a
            finished stage of the kind asked.
    """
    topic = topic or await topic_of(db, task, lock=True)
    need_assignees_assistant(actor, task, label, topic)
    current = await db.get(Stage, task.stage_id)
    assert current is not None
    if CATEGORY[current.kind] == Category.Finished:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {"code": "finished", "message": f"{label} is finished already: {task.outcome}"},
        )
    if not outcome.strip():
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Close with an outcome: a line or two and the MR or issue link",
        )
    stages = await stages_of(db, current.workflow_id)
    if task.type == TaskType.Promise:
        kind = (
            StageKind.Withdrawn
            if cancelled
            else StageKind.NotDelivered
            if missed
            else StageKind.Delivered
        )
    else:
        kind = StageKind.Cancelled if cancelled else StageKind.Done
    stage = first_of_kind(stages, kind)
    if stage is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"The workflow of {label} has no {kind} stage"
        )
    moment = now()
    task.stage_id = stage.id
    task.outcome = outcome.strip()
    task.finished_at = moment
    task.waiting = None
    record(
        db,
        task,
        "closed",
        actor,
        {"from": current.name, "to": stage.name, "kind": stage.kind.value, "outcome": task.outcome},
    )
    recipients = await task_event(db, actor, task, "closed", outcome=task.outcome)
    if topic is not None:
        topic.outcome = task.outcome
        if topic.status != TopicStatus.Closed:
            _, more = await post(db, actor, topic, task.outcome, MessageKind.Closed, None, [])
            recipients |= more
            topic.status = TopicStatus.Closed
            topic.closed_at = moment
            topic.updated_at = moment
            recipients |= await status_event(db, actor, topic)
    return recipients


async def detail(
    request: Request,
    db: AsyncSession,
    actor: Actor,
    task: Task,
    limit: int = 50,
    from_unread: bool = False,
) -> TaskDetail:
    """Build a task with its description, timeline and Topic.

    Args:
        request: The incoming request, for the instance's settings.
        db: Database session.
        actor: The caller.
        task: The task.
        limit: How many of its Topic's Messages.
        from_unread: Start at the caller's first unread Message when more are unread.
    """
    (summary,) = await task_outs(db, [task])
    topic = await topic_of(db, task)
    shown = None
    if topic is not None:
        messages = await feed(db, actor, topic, None, None, limit, from_unread)
        shown = await topic_detail(request, db, actor, topic, messages)
    return TaskDetail(
        **summary.model_dump(),
        description=task.description,
        timeline=await timeline(db, task),
        topic=shown,
    )


async def assignee_by_name(db: AsyncSession, team_id: int, name: str) -> User:
    """Return a human of the Team by pseudonym, any case.

    Args:
        db: Database session.
        team_id: The Team.
        name: The pseudonym.

    Raises:
        HTTPException: 422 when nobody in the Team is called so; the detail lists the Members.
    """
    members = list(
        await db.scalars(
            select(User).join(Member, Member.user_id == User.id).where(Member.team_id == team_id)
        )
    )
    wanted = name.strip().lstrip("@").lower()
    for user in members:
        if user.pseudonym and user.pseudonym.lower() == wanted:
            return user
    raise HTTPException(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        f"Nobody in the Team is called {name!r}. Members: "
        + ", ".join(sorted(u.pseudonym for u in members if u.pseudonym)),
    )


async def held_task(db: AsyncSession, actor: Actor) -> Task | None:
    """Return the one unfinished task whose Topic the calling Assistant holds, if exactly one.

    Args:
        db: Database session.
        actor: The caller.
    """
    if actor.assistant is None:
        return None
    rows = list(
        await db.scalars(
            select(Task)
            .join(Topic, Topic.task_id == Task.id)
            .where(Topic.holder_assistant_id == actor.assistant.id, Task.finished_at.is_(None))
            .limit(2)
        )
    )
    return rows[0] if len(rows) == 1 else None


@router.get("/team/{team}/workflow")
async def list_workflows(team: str, actor: ActorDep, db: DB) -> list[WorkflowOut]:
    """Return the Team's workflows with their stages, and which Areas use each.

    Args:
        team: The Team's slug.
        actor: The caller.
        db: Database session.

    Raises:
        HTTPException: 404 when the caller is not in the Team.
    """
    require_reader(actor)
    found, _ = await team_for(db, team, actor.user.id)
    workflows = list(
        await db.scalars(select(Workflow).where(Workflow.team_id == found.id).order_by(Workflow.id))
    )
    areas = list(await db.scalars(select(Area).where(Area.team_id == found.id).order_by(Area.id)))
    result = []
    for workflow in workflows:
        stages = await stages_of(db, workflow.id)
        result.append(
            WorkflowOut(
                type=workflow.type,
                areas=[a.slug for a in areas if a.workflow_id == workflow.id],
                stages=[
                    StageOut(name=s.name, kind=s.kind, category=CATEGORY[s.kind]) for s in stages
                ],
            )
        )
    return result


@router.get("/team/{team}/task")
async def list_tasks(
    team: str,
    actor: ActorDep,
    db: DB,
    area: Annotated[str | None, Query()] = None,
    category: Annotated[Category | None, Query()] = None,
    assignee: Annotated[str | None, Query()] = None,
    type_filter: Annotated[TaskType | None, Query(alias="type")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[TaskOut]:
    """List a Team's tasks, highest first within their order.

    Args:
        team: The Team's slug.
        actor: The caller.
        db: Database session.
        area: Only this Area, by slug.
        category: Only to do, in progress or finished.
        assignee: Only those assigned to this pseudonym; ``-`` for unassigned.
        type_filter: Only tasks or only promises.
        limit: At most this many.

    Raises:
        HTTPException: 404 when the caller is not in the Team or there is no such Area.
    """
    require_reader(actor)
    found, _ = await team_for(db, team, actor.user.id)
    query = select(Task).join(Stage, Stage.id == Task.stage_id).where(Task.team_id == found.id)
    if area is not None:
        row = await find_area(db, found.id, area)
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No such Area")
        query = query.where(Task.area_id == row.id)
    if category is not None:
        query = query.where(
            Stage.kind.in_([kind for kind, cat in CATEGORY.items() if cat == category])
        )
    if assignee == "-":
        query = query.where(Task.assignee_id.is_(None))
    elif assignee is not None:
        user = await assignee_by_name(db, found.id, assignee)
        query = query.where(Task.assignee_id == user.id)
    if type_filter is not None:
        query = query.where(Task.type == type_filter)
    tasks = list(await db.scalars(query.order_by(Task.rank, Task.number).limit(limit)))
    return await task_outs(db, tasks)


@router.post("/team/{team}/task", status_code=status.HTTP_201_CREATED)
async def create_task(
    request: Request, team: str, body: TaskIn, actor: ActorDep, db: DB
) -> TaskDetail:
    """Put a task in the backlog: planning, so the tracker must be on (decision 0032).

    Its source is the task within which it is created: the one given, or the one whose Topic
    the calling Assistant holds (decision 0031).

    Args:
        request: The incoming request.
        team: The Team's slug.
        body: The task.
        actor: The caller.
        db: Database session.

    Raises:
        HTTPException: 404 when there is no such Team, Area, parent or source for the caller;
            403 when the caller may not write there; 409 ``no_tracker`` without the tracker;
            422 for an unknown assignee or a parent that cannot hold it.
    """
    require_reader(actor)
    found, _ = await team_for(db, team, actor.user.id)
    await require_writer(db, actor, found.id)
    locked = await db.scalar(select(Team).where(Team.id == found.id).with_for_update())
    assert locked is not None
    need_tracker(locked)
    area = await find_area(db, found.id, body.area)
    if area is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No Area {body.area!r} in the Team")
    parent = None
    if body.parent is not None:
        parent, _ = await task_for(db, team, body.parent, actor)
        await check_parent(db, parent, body.type)
    source = None
    if body.source is not None:
        source, _ = await task_for(db, team, body.source, actor)
    else:
        source = await held_task(db, actor)
    assignee = await assignee_by_name(db, found.id, body.assignee) if body.assignee else None
    workflow = await workflow_for(db, found.id, body.type, area)
    stage = first_of(await stages_of(db, workflow.id), Category.ToDo)
    task = await new_task(
        db,
        actor,
        locked,
        area,
        body.title,
        body.type,
        stage,
        assignee.id if assignee else None,
        body.description,
        parent.id if parent else None,
        source.id if source else None,
    )
    task.period_start, task.period_end = body.period_start, body.period_end
    for key in body.links:
        await add_link(db, actor, task, key)
    recipients = await task_event(db, actor, task, "created")
    await db.commit()
    request.app.state.bus.wake(recipients)
    return await detail(request, db, actor, task)


async def check_parent(db: AsyncSession, parent: Task, type_: TaskType) -> None:
    """Refuse a parent that cannot hold a child of this type (decision 0031).

    A promise holds either promises or tasks, never both; a task holds only subtasks, one level
    deep; a subtask holds nothing.

    Args:
        db: Database session.
        parent: The would-be parent.
        type_: The child's type.

    Raises:
        HTTPException: 422 with the rule broken.
    """
    if parent.type == TaskType.Task:
        if type_ != TaskType.Task or (
            parent.parent_id is not None
            and (
                await db.scalar(select(Task.type).where(Task.id == parent.parent_id))
                == TaskType.Task
            )
        ):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "A task holds only subtasks, and a subtask holds nothing",
            )
        return
    kinds = set(await db.scalars(select(Task.type).where(Task.parent_id == parent.id).distinct()))
    if kinds and type_ not in kinds:
        held = "promises" if TaskType.Promise in kinds else "tasks"
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"{ref(parent.number)} holds {held}; a promise holds either promises or tasks, never "
            "both. Move its tasks into sub-promises first.",
        )


@router.get("/team/{team}/task/{number}")
async def read_task(
    request: Request,
    team: str,
    number: int,
    actor: ActorDep,
    db: DB,
    limit: Annotated[int, Query(ge=1, le=FEED_LIMIT)] = 50,
    from_unread: Annotated[bool, Query()] = False,
) -> TaskDetail:
    """Return a task with its description, timeline and Topic.

    Args:
        request: The incoming request.
        team: The Team's slug.
        number: The task's number.
        actor: The caller.
        db: Database session.
        limit: How many of its Topic's Messages.
        from_unread: Start at the first unread Message when more than ``limit`` are unread.

    Raises:
        HTTPException: 404 when there is no such task in the caller's Teams.
    """
    task, _ = await task_for(db, team, number, actor)
    return await detail(request, db, actor, task, limit, from_unread)


@router.patch("/team/{team}/task/{number}")
async def edit_task(
    request: Request, team: str, number: int, body: TaskPatch, actor: ActorDep, db: DB
) -> TaskOut:
    """Edit a task's title, description or Area; the timeline keeps every description.

    Args:
        request: The incoming request.
        team: The Team's slug.
        number: The task's number.
        body: What changes.
        actor: The caller.
        db: Database session.

    Raises:
        HTTPException: 404 when there is no such task or Area; 403 when the caller may not
            write there.
    """
    task, found = await task_for(db, team, number, actor, write=True)
    topic = await topic_of(db, task, lock=True)
    if body.title is not None and body.title.strip() != task.title:
        record(db, task, "retitled", actor, {"from": task.title, "to": body.title.strip()})
        task.title = body.title.strip()
        if topic is not None:
            topic.title = task.title
    if body.description is not None and body.description != task.description:
        record(db, task, "described", actor, {"text": body.description})
        task.description = body.description
    for field in ("period_start", "period_end"):
        value = getattr(body, field)
        if field in body.model_fields_set and value != getattr(task, field):
            record(db, task, "period", actor, {field: value.isoformat() if value else None})
            setattr(task, field, value)
    if body.area is not None:
        area = await find_area(db, found.id, body.area)
        if area is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"No Area {body.area!r} in the Team")
        if area.id != task.area_id:
            former = await db.get(Area, task.area_id)
            record(
                db, task, "area", actor, {"from": former.name if former else "", "to": area.name}
            )
            task.area_id = area.id
            if topic is not None:
                topic.area_id = area.id
    recipients = await task_event(db, actor, task, "edited")
    await db.commit()
    request.app.state.bus.wake(recipients)
    (out,) = await task_outs(db, [task])
    return out


@router.post("/team/{team}/task/{number}/take")
async def take_task(
    request: Request, team: str, number: int, body: TakeIn, actor: ActorDep, db: DB
) -> TaskDetail:
    """Take a task into work: assigned, moved to work, its Topic opened and held (0032).

    A task in the backlog moves to the first stage of work. A task with no assignee is assigned
    to the caller's human; one assigned to another human only with ``reassign``.

    Args:
        request: The incoming request.
        team: The Team's slug.
        number: The task's number.
        body: The first Message and whether to reassign.
        actor: The Assistant.
        db: Database session.

    Raises:
        HTTPException: 404 when there is no such task; 403 without an Assistant, or when it may
            not write there; 409 ``finished`` for a finished task, ``assigned`` for one assigned
            to another human without ``reassign``.
    """
    if actor.assistant is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only an Assistant takes a task")
    task, found = await task_for(db, team, number, actor, write=True)
    label = f"{found.slug}/{ref(task.number)}"
    current = await db.get(Stage, task.stage_id)
    assert current is not None
    if CATEGORY[current.kind] == Category.Finished:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {"code": "finished", "message": f"{label} is finished; a fix is a new task"},
        )
    recipients: set[int] = set()
    if task.assignee_id not in (None, actor.user.id) and not body.reassign:
        owner = await db.get(User, task.assignee_id)
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "code": "assigned",
                "message": f"{label} is assigned to {owner.pseudonym if owner else 'someone'}; "
                "take it only if your user takes it over, with reassign=true.",
            },
        )
    if task.assignee_id != actor.user.id:
        record(db, task, "assigned", actor, {"from": task.assignee_id, "to": actor.user.id})
        task.assignee_id = actor.user.id
        recipients |= await task_event(db, actor, task, "assigned")
    if CATEGORY[current.kind] == Category.ToDo:
        stage = start_of(await stages_of(db, current.workflow_id))
        if stage.id != current.id:
            recipients |= await move_to(db, actor, task, stage, stage.name, {})
    topic = await topic_of(db, task, lock=True)
    if topic is None:
        area = await db.get(Area, task.area_id)
        assert area is not None
        topic = Topic(
            team_id=found.id,
            number=None,
            task_id=task.id,
            area_id=task.area_id,
            title=task.title,
            issue=await first_link(db, task.id),
            status=TopicStatus.Open,
            outcome="",
            created_by=actor.user.id,
            holder_assistant_id=actor.assistant.id,
            last_number=0,
            turns_since_human=0,
        )
        db.add(topic)
        await db.flush()
        holder = (await assistants_by_id(db, {actor.assistant.id}))[actor.assistant.id]
        recipients |= await add_event(
            db,
            found.id,
            "topic",
            topic_head(topic, found, area, task.number)
            | {
                "author": actor.user.pseudonym,
                "author_assistant": holder.key,
                "holder": holder.key,
                "to": None,
                "to_assistant": None,
                "to_assistant_name": None,
                "meant_for": None,
            },
        )
        _, more = await post(
            db,
            actor,
            topic,
            body.body or f"Took {ref(task.number)}: {task.title}",
            MessageKind.Message,
            None,
            [],
            with_human=body.with_human,
            counts_as_turn=False,
        )
        recipients |= more
    else:
        recipients |= await hold(db, actor, topic)
    await db.commit()
    request.app.state.bus.wake(recipients)
    return await detail(request, db, actor, task)


@router.post("/team/{team}/task/{number}/stage")
async def change_stage(
    request: Request, team: str, number: int, body: StageIn, actor: ActorDep, db: DB
) -> TaskOut:
    """Move a task to another stage of work, maybe passing some at once (decision 0032).

    Moves are free within work, back ones included; a finished task is final, and finishing
    one goes through ``close``.

    Args:
        request: The incoming request.
        team: The Team's slug.
        number: The task's number.
        body: The stage, the stages skipped with reasons, and a comment.
        actor: The assignee's Assistant.
        db: Database session.

    Raises:
        HTTPException: 404 when there is no such task; 403 for a human or when the caller may
            not write there; 409 ``not_assignee`` for another Assistant, ``finished`` for a
            finished task; 422 for an unknown stage, a finished one, or a skipped stage that is
            not in the workflow.
    """
    task, found = await task_for(db, team, number, actor, write=True)
    label = f"{found.slug}/{ref(task.number)}"
    need_assignees_assistant(actor, task, label, None)
    current = await db.get(Stage, task.stage_id)
    assert current is not None
    if CATEGORY[current.kind] == Category.Finished:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {"code": "finished", "message": f"{label} is finished; a fix is a new task"},
        )
    stage = await stage_by_name(db, task, body.stage, label)
    if CATEGORY[stage.kind] == Category.Finished:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"Finish {label} with close, which takes the outcome",
        )
    skipped = []
    for name, reason in body.skip.items():
        passed = await stage_by_name(db, task, name, label)
        record(
            db,
            task,
            "skipped",
            actor,
            {"stage": passed.name, "kind": passed.kind.value, "reason": reason.strip()},
        )
        skipped.append(f"{passed.name}: {reason.strip()}" if reason.strip() else passed.name)
    line = stage.name
    if skipped:
        line += f" (skipped {'; '.join(skipped)})"
    if body.comment.strip():
        line += f" — {body.comment.strip()}"
    recipients = await move_to(
        db, actor, task, stage, line, {"comment": body.comment.strip()} if body.comment else {}
    )
    await db.commit()
    request.app.state.bus.wake(recipients)
    (out,) = await task_outs(db, [task])
    return out


async def _wait(
    request: Request, db: AsyncSession, actor: Actor, team: str, number: int, what: str | None
) -> TaskOut:
    """Mark or end an external wait over a task's stage (decision 0033).

    Args:
        request: The incoming request.
        db: Database session.
        actor: The assignee's Assistant.
        team: The Team's slug.
        number: The task's number.
        what: Whom or what it waits for; ``None`` when the wait is over.

    Raises:
        HTTPException: 404 when there is no such task; 403 for a human or when the caller may
            not write there; 409 ``not_assignee`` for another Assistant, ``finished`` for a
            finished task.
    """
    task, found = await task_for(db, team, number, actor, write=True)
    label = f"{found.slug}/{ref(task.number)}"
    need_assignees_assistant(actor, task, label, None)
    if task.finished_at is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, {"code": "finished", "message": f"{label} is finished"}
        )
    recipients: set[int] = set()
    if what is not None:
        task.waiting = what.strip()
        record(db, task, "waiting", actor, {"what": task.waiting})
        line = f"Waiting: {task.waiting}"
        recipients |= await task_event(db, actor, task, "waiting", what=task.waiting)
    elif task.waiting is not None:
        record(db, task, "resumed", actor, {"what": task.waiting})
        line = f"Resumed after waiting: {task.waiting}"
        task.waiting = None
        recipients |= await task_event(db, actor, task, "resumed")
    else:
        line = ""
    topic = await topic_of(db, task, lock=True)
    if topic is not None and line:
        _, more = await post(db, actor, topic, line, MessageKind.Progress, None, [])
        recipients |= more
    await db.commit()
    request.app.state.bus.wake(recipients)
    (out,) = await task_outs(db, [task])
    return out


@router.post("/team/{team}/task/{number}/wait")
async def wait_task(
    request: Request, team: str, number: int, body: WaitIn, actor: ActorDep, db: DB
) -> TaskOut:
    """Mark that a task waits for something outside the Team; its stage stays (decision 0033).

    Args:
        request: The incoming request.
        team: The Team's slug.
        number: The task's number.
        body: Whom or what it waits for.
        actor: The assignee's Assistant.
        db: Database session.

    Raises:
        HTTPException: 404 when there is no such task; 403 for a human or when the caller may
            not write there; 409 ``not_assignee`` for another Assistant, ``finished`` for a
            finished task.
    """
    return await _wait(request, db, actor, team, number, body.what)


@router.post("/team/{team}/task/{number}/resume")
async def resume_task(request: Request, team: str, number: int, actor: ActorDep, db: DB) -> TaskOut:
    """Mark that a task's external wait is over.

    Args:
        request: The incoming request.
        team: The Team's slug.
        number: The task's number.
        actor: The assignee's Assistant.
        db: Database session.

    Raises:
        HTTPException: 404 when there is no such task; 403 for a human or when the caller may
            not write there; 409 ``not_assignee`` for another Assistant, ``finished`` for a
            finished task.
    """
    return await _wait(request, db, actor, team, number, None)


@router.post("/team/{team}/task/{number}/close")
async def close(
    request: Request, team: str, number: int, body: CloseIn, actor: ActorDep, db: DB
) -> TaskOut:
    """Finish a task as done or cancelled, with an outcome; its Topic closes (decision 0032).

    Args:
        request: The incoming request.
        team: The Team's slug.
        number: The task's number.
        body: The outcome, and whether it is cancelled.
        actor: The assignee's Assistant.
        db: Database session.

    Raises:
        HTTPException: 404 when there is no such task; 403 for a human or when the caller may
            not write there; 409 ``not_assignee`` for another Assistant, ``finished`` when it is
            finished already; 422 without an outcome.
    """
    task, found = await task_for(db, team, number, actor, write=True)
    recipients = await close_task(
        db,
        actor,
        task,
        body.outcome,
        body.cancelled,
        f"{found.slug}/{ref(task.number)}",
        missed=body.missed,
    )
    await db.commit()
    request.app.state.bus.wake(recipients)
    (out,) = await task_outs(db, [task])
    return out


@router.post("/team/{team}/task/{number}/link")
async def link_task(
    request: Request, team: str, number: int, body: LinkIn, actor: ActorDep, db: DB
) -> TaskOut:
    """Link a task to an external issue; no sync (decision 0031).

    Args:
        request: The incoming request.
        team: The Team's slug.
        number: The task's number.
        body: The issue's key and address.
        actor: The caller.
        db: Database session.

    Raises:
        HTTPException: 404 when there is no such task; 403 when the caller may not write there.
    """
    task, _ = await task_for(db, team, number, actor, write=True)
    await add_link(db, actor, task, body.key, body.url)
    topic = await topic_of(db, task, lock=True)
    await db.flush()
    if topic is not None and not topic.issue:
        topic.issue = await first_link(db, task.id)
    await db.commit()
    (out,) = await task_outs(db, [task])
    return out


@router.post("/team/{team}/task/{number}/assign")
async def assign_task(
    request: Request, team: str, number: int, body: AssignIn, actor: ActorDep, db: DB
) -> TaskOut:
    """Assign a task to a human of the Team, or unassign it: planning (decision 0031).

    Args:
        request: The incoming request.
        team: The Team's slug.
        number: The task's number.
        body: The assignee's pseudonym, or ``None``.
        actor: The caller.
        db: Database session.

    Raises:
        HTTPException: 404 when there is no such task; 403 when the caller may not write there;
            409 ``no_tracker`` without the tracker, ``finished`` for a finished task; 422 for
            an unknown pseudonym.
    """
    task, found = await task_for(db, team, number, actor, write=True)
    need_tracker(found)
    if task.finished_at is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {"code": "finished", "message": f"{found.slug}/{ref(task.number)} is finished"},
        )
    user = await assignee_by_name(db, found.id, body.assignee) if body.assignee else None
    new_id = user.id if user else None
    recipients: set[int] = set()
    if new_id != task.assignee_id:
        record(db, task, "assigned", actor, {"from": task.assignee_id, "to": new_id})
        task.assignee_id = new_id
        recipients = await task_event(db, actor, task, "assigned")
    await db.commit()
    request.app.state.bus.wake(recipients)
    (out,) = await task_outs(db, [task])
    return out


@router.post("/team/{team}/task/{number}/order")
async def order_task(
    request: Request, team: str, number: int, body: OrderIn, actor: ActorDep, db: DB
) -> TaskOut:
    """Place a task right above or below another: planning by a human (decision 0032).

    Args:
        request: The incoming request.
        team: The Team's slug.
        number: The task's number.
        body: The task it goes above or below.
        actor: A human of the Team in the web.
        db: Database session.

    Raises:
        HTTPException: 404 when there is no such task; 403 for a plugin; 409 ``no_tracker``
            without the tracker; 422 without exactly one of ``before`` and ``after``.
    """
    if not actor.is_human:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Ordering tasks is done in the web")
    if (body.before is None) == (body.after is None):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Give exactly one of before and after"
        )
    task, found = await task_for(db, team, number, actor, write=True)
    need_tracker(found)
    other, _ = await task_for(db, team, body.before or body.after or 0, actor)
    if body.before is not None:
        neighbour = await db.scalar(
            select(func.max(Task.rank)).where(
                Task.team_id == found.id, Task.id != task.id, Task.rank < other.rank
            )
        )
        task.rank = (other.rank + neighbour) / 2 if neighbour is not None else other.rank - 1.0
    else:
        neighbour = await db.scalar(
            select(func.min(Task.rank)).where(
                Task.team_id == found.id, Task.id != task.id, Task.rank > other.rank
            )
        )
        task.rank = (other.rank + neighbour) / 2 if neighbour is not None else other.rank + 1.0
    await db.commit()
    (out,) = await task_outs(db, [task])
    return out


@router.post("/moves")
async def post_moves(body: MovesIn, actor: ActorDep, db: DB) -> MovesOut:
    """Keep the intervals of whose move it was in the calling session (decision 0033).

    The plugin's hooks mark the human's prompts and the Assistant's stops; the session's watch
    turns them into intervals and posts them here. They are kept as the raw fact, by session:
    which task the time belongs to is decided when the measurement reads it. An interval longer
    than 12 hours, ending before it starts, or posted twice is dropped.

    Args:
        body: The intervals.
        actor: The session's Assistant.
        db: Database session.

    Raises:
        HTTPException: 403 without an Assistant.
    """
    if actor.assistant is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only an Assistant's session has moves")
    rows = [
        {
            "assistant_id": actor.assistant.id,
            "user_id": actor.user.id,
            "move": interval.move,
            "started_at": interval.start,
            "ended_at": interval.end,
        }
        for interval in body.intervals
        if timedelta(0) < interval.end - interval.start <= MOVE_MAX
    ]
    recorded = 0
    if rows:
        result = await db.execute(
            insert(Move).values(rows).on_conflict_do_nothing().returning(Move.id)
        )
        recorded = len(result.all())
    await db.commit()
    return MovesOut(recorded=recorded)
