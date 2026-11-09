"""Plans: a Team's plan for a period, its rows, marks and result (decision 0037).

A plan is a draft until a human approves it and is closed by a human after its period. It holds
promises and tasks by membership; a row's mark is set by itself when it joins. An Assistant creates
a plan and fills its draft; approving, closing, adding work after approval, correcting a mark,
writing what is dropped and postponing are a human's.
"""

from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from coloqo_server.api.tasks import TaskOut, need_tracker, task_for, task_outs
from coloqo_server.api.teams import team_for
from coloqo_server.api.topics import pseudonyms, ref
from coloqo_server.events import add_event
from coloqo_server.models import (
    CATEGORY,
    Category,
    Plan,
    PlanItem,
    PlanMark,
    PlanResult,
    Stage,
    StageKind,
    Task,
    TaskType,
    Team,
)
from coloqo_server.planning import (
    finished_before,
    join,
    joinable_under,
    local_day,
    today_of,
    zone_of,
)
from coloqo_server.security import DB, Actor, ActorDep, now, require_reader, require_writer
from coloqo_server.tracker import record

router = APIRouter(tags=["plans"])

State = Literal["draft", "approved", "closed"]


class PlanIn(BaseModel):
    """A new plan, a draft (decision 0037).

    Attributes:
        name: What people call it, e.g. ``November 2026``.
        period_start: Its first day.
        period_end: Its last day.
    """

    name: str = Field(min_length=1, max_length=100)
    period_start: date
    period_end: date

    @model_validator(mode="after")
    def ordered(self) -> PlanIn:
        """Refuse a period that ends before it starts.

        Raises:
            ValueError: The last day is before the first.
        """
        if self.period_end < self.period_start:
            raise ValueError("The period ends before it starts")
        return self


class PlanAddIn(BaseModel):
    """Work to add to a plan: a promise brings its unfinished tasks.

    Attributes:
        tasks: The numbers of the promises and tasks.
    """

    tasks: list[int] = Field(min_length=1, max_length=200)


class PlanItemPatch(BaseModel):
    """A human's change to a row (decision 0037).

    Attributes:
        mark: ``found`` or ``off_plan``, after approval.
        dropped: For off-plan work: what it drops from the plan.
        postponed: ``true`` with a ``reason`` postpones the row; ``false`` undoes it.
        reason: Why it is postponed.
    """

    mark: Literal["found", "off_plan"] | None = None
    dropped: str | None = Field(default=None, max_length=2000)
    postponed: bool | None = None
    reason: str | None = Field(default=None, max_length=500)


class PlanOut(BaseModel):
    """A plan, as lists show it.

    Attributes:
        number: Its number among the Team's plans.
        name: Its name.
        period_start: Its first day.
        period_end: Its last day.
        state: ``draft``, ``approved`` or ``closed``.
        created_by: Who made it.
        approved_by: Who approved it.
        approved_at: When.
        closed_by: Who closed it.
        closed_at: When.
        rows: How many promises and tasks it holds.
    """

    number: int
    name: str
    period_start: date
    period_end: date
    state: State
    created_by: str | None
    approved_by: str | None
    approved_at: datetime | None
    closed_by: str | None
    closed_at: datetime | None
    rows: int


class PlanRowOut(BaseModel):
    """A promise or task in a plan.

    Attributes:
        task: The promise or task.
        mark: ``planned``, ``found`` or ``off_plan``.
        dropped: For off-plan work: what it drops; empty until a human names it.
        joined_at: When it joined.
        postponed: Whether a human postponed it in this plan.
        postponed_reason: Why.
        postponed_by: Who.
        result: ``done``, ``cancelled`` or ``not_done``, once the plan is closed.
        carried_from: The name of the earlier closed plan where it was not done, if any.
    """

    task: TaskOut
    mark: PlanMark
    dropped: str
    joined_at: datetime
    postponed: bool
    postponed_reason: str
    postponed_by: str | None
    result: PlanResult | None
    carried_from: str | None


class PlanSummary(BaseModel):
    """What a plan came to, counted over its tasks (promises apart).

    Attributes:
        planned: Planned tasks.
        planned_done: Of them, done in the period (once closed: as fixed).
        postponed: Rows postponed.
        found: Found tasks.
        off_plan: Off-plan tasks.
        dropped_unnamed: Off-plan tasks that do not say yet what they drop.
    """

    planned: int
    planned_done: int
    postponed: int
    found: int
    off_plan: int
    dropped_unnamed: int


class PlanDetail(PlanOut):
    """A plan with its rows, what it came to, and, for a draft, what the previous one left.

    Attributes:
        items: Its rows, promises first, then by number.
        summary: What it came to.
        previous_unfinished: For a draft: tasks of the previous closed plan not done there, not
            in this one and not finished before this one's period.
    """

    items: list[PlanRowOut]
    summary: PlanSummary
    previous_unfinished: list[int]


def state_of(plan: Plan) -> State:
    """Return a plan's state, read from its two moments.

    Args:
        plan: The plan.
    """
    if plan.closed_at is not None:
        return "closed"
    return "approved" if plan.approved_at is not None else "draft"


def need_human(actor: Actor, what: str) -> None:
    """Refuse a plan's act that is a human's (decision 0037).

    Args:
        actor: The caller.
        what: The act, for the message.

    Raises:
        HTTPException: 403 for an Assistant.
    """
    if not actor.is_human:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"{what} is a human's: ask your user to do it in the web",
        )


async def plan_for(
    db: AsyncSession, team: str, number: int, actor: Actor, write: bool = False
) -> tuple[Plan, Team]:
    """Return a Team's plan for a member; for a write, lock it and check the tracker.

    Args:
        db: Database session.
        team: The Team's slug.
        number: The plan's number.
        actor: The caller.
        write: The caller is about to change it.

    Raises:
        HTTPException: 404 when there is no such plan in the caller's Teams; 403 when the caller
            may not write there; 409 ``no_tracker`` for a write without the tracker.
    """
    require_reader(actor)
    found, _ = await team_for(db, team, actor.user.id)
    query = select(Plan).where(Plan.team_id == found.id, Plan.number == number)
    plan = await db.scalar(query.with_for_update() if write else query)
    if plan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No plan {number} in the Team")
    if write:
        await require_writer(db, actor, found.id)
        need_tracker(found)
    return plan, found


async def plan_outs(db: AsyncSession, plans: list[Plan]) -> list[PlanOut]:
    """Build the views of plans.

    Args:
        db: Database session.
        plans: The plans.
    """
    users = await pseudonyms(
        db,
        {p.created_by for p in plans}
        | {p.approved_by for p in plans}
        | {p.closed_by for p in plans},
    )
    counts = dict(
        (
            await db.execute(
                select(PlanItem.plan_id, func.count())
                .where(PlanItem.plan_id.in_([p.id for p in plans]))
                .group_by(PlanItem.plan_id)
            )
        ).all()
    )
    return [
        PlanOut(
            number=p.number,
            name=p.name,
            period_start=p.period_start,
            period_end=p.period_end,
            state=state_of(p),
            created_by=users.get(p.created_by),
            approved_by=users.get(p.approved_by) if p.approved_by else None,
            approved_at=p.approved_at,
            closed_by=users.get(p.closed_by) if p.closed_by else None,
            closed_at=p.closed_at,
            rows=counts.get(p.id, 0),
        )
        for p in plans
    ]


async def previous_plan(db: AsyncSession, plan: Plan) -> Plan | None:
    """Return the Team's closed plan just before this one, if any.

    Args:
        db: Database session.
        plan: The plan.
    """
    return await db.scalar(
        select(Plan)
        .where(
            Plan.team_id == plan.team_id,
            Plan.closed_at.is_not(None),
            Plan.period_end < plan.period_start,
        )
        .order_by(Plan.period_end.desc())
        .limit(1)
    )


async def plan_detail(db: AsyncSession, plan: Plan) -> PlanDetail:
    """Build a plan's full view.

    Args:
        db: Database session.
        plan: The plan.
    """
    (head,) = await plan_outs(db, [plan])
    items = list(await db.scalars(select(PlanItem).where(PlanItem.plan_id == plan.id)))
    tasks = {
        t.id: t
        for t in await db.scalars(select(Task).where(Task.id.in_([i.task_id for i in items])))
    }
    outs = {o.number: o for o in await task_outs(db, list(tasks.values()))}
    users = await pseudonyms(db, {i.postponed_by for i in items})
    carried: dict[int, str] = {}
    earlier = list(
        await db.execute(
            select(PlanItem.task_id, Plan.name, Plan.period_end)
            .join(Plan, Plan.id == PlanItem.plan_id)
            .where(
                PlanItem.task_id.in_(list(tasks)),
                Plan.team_id == plan.team_id,
                Plan.closed_at.is_not(None),
                Plan.period_end < plan.period_start,
                PlanItem.result == PlanResult.NotDone,
            )
            .order_by(Plan.period_end)
        )
    )
    for task_id, name, _ in earlier:
        carried[task_id] = name
    rows = []
    for item in items:
        task = tasks[item.task_id]
        rows.append(
            PlanRowOut(
                task=outs[task.number],
                mark=item.mark,
                dropped=item.dropped,
                joined_at=item.joined_at,
                postponed=item.postponed_at is not None,
                postponed_reason=item.postponed_reason,
                postponed_by=users.get(item.postponed_by) if item.postponed_by else None,
                result=item.result,
                carried_from=carried.get(task.id),
            )
        )
    rows.sort(key=lambda r: (r.task.type != TaskType.Promise, r.task.number))
    work = [r for r in rows if r.task.type != TaskType.Promise]
    planned = [r for r in work if r.mark == PlanMark.Planned]
    zone = await zone_of(db, plan)

    def done(row: PlanRowOut) -> bool:
        """Whether a row counts as done: as fixed at closing, or finished by the period's end.

        Args:
            row: The row.
        """
        if row.result is not None:
            return row.result == PlanResult.Done
        finished = row.task.finished_at
        return (
            row.task.stage_kind in (StageKind.Done, StageKind.Delivered)
            and finished is not None
            and local_day(finished, zone) <= plan.period_end
        )

    summary = PlanSummary(
        planned=len(planned),
        planned_done=sum(1 for r in planned if done(r)),
        postponed=sum(1 for r in rows if r.postponed),
        found=sum(1 for r in work if r.mark == PlanMark.Found),
        off_plan=sum(1 for r in work if r.mark == PlanMark.OffPlan),
        dropped_unnamed=sum(1 for r in work if r.mark == PlanMark.OffPlan and not r.dropped),
    )
    previous: list[int] = []
    if state_of(plan) == "draft":
        before = await previous_plan(db, plan)
        if before is not None:
            for task in await db.scalars(
                select(Task)
                .join(PlanItem, PlanItem.task_id == Task.id)
                .where(PlanItem.plan_id == before.id, PlanItem.result == PlanResult.NotDone)
                .order_by(Task.number)
            ):
                # The same rule as every way in: not work finished before this period (0037).
                if task.id not in tasks and not await finished_before(db, plan, task):
                    previous.append(task.number)
    return PlanDetail(
        **head.model_dump(), items=rows, summary=summary, previous_unfinished=previous
    )


async def plan_event(db: AsyncSession, team: Team, plan: Plan, change: str) -> set[int]:
    """Tell the Team that a plan changed, so the web refreshes it.

    Args:
        db: Database session.
        team: The Team.
        plan: The plan.
        change: ``created``, ``added``, ``removed``, ``row``, ``approved``, ``closed``.

    Returns:
        The Users who got the event, to wake after the commit.
    """
    data = {"team": team.slug, "plan": plan.number, "name": plan.name, "event": change}
    return await add_event(db, team.id, "plan", data)


@router.get("/team/{team}/plan")
async def list_plans(team: str, actor: ActorDep, db: DB) -> list[PlanOut]:
    """List a Team's plans, the latest period first.

    Args:
        team: The Team's slug.
        actor: The caller.
        db: Database session.

    Raises:
        HTTPException: 404 when the caller is not in the Team.
    """
    require_reader(actor)
    found, _ = await team_for(db, team, actor.user.id)
    plans = list(
        await db.scalars(
            select(Plan).where(Plan.team_id == found.id).order_by(Plan.period_start.desc())
        )
    )
    return await plan_outs(db, plans)


@router.post("/team/{team}/plan", status_code=status.HTTP_201_CREATED)
async def create_plan(
    request: Request, team: str, body: PlanIn, actor: ActorDep, db: DB
) -> PlanDetail:
    """Create a plan, a draft; its period must not overlap another of the Team's plans (0037).

    Args:
        request: The incoming request.
        team: The Team's slug.
        body: The plan.
        actor: The caller: a human or an Assistant.
        db: Database session.

    Raises:
        HTTPException: 404 when the caller is not in the Team; 403 when it may not write there;
            409 ``no_tracker`` without the tracker, ``overlap`` when the period overlaps a plan.
    """
    require_reader(actor)
    found, _ = await team_for(db, team, actor.user.id)
    await require_writer(db, actor, found.id)
    locked = await db.scalar(select(Team).where(Team.id == found.id).with_for_update())
    assert locked is not None
    need_tracker(locked)
    other = await db.scalar(
        select(Plan).where(
            Plan.team_id == found.id,
            Plan.period_start <= body.period_end,
            Plan.period_end >= body.period_start,
        )
    )
    if other is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "code": "overlap",
                "message": f"The period overlaps the plan «{other.name}» "
                f"({other.period_start}..{other.period_end}); a Team's plans do not overlap",
            },
        )
    number = (await db.scalar(select(func.max(Plan.number)).where(Plan.team_id == found.id))) or 0
    plan = Plan(
        team_id=found.id,
        number=number + 1,
        name=body.name.strip(),
        period_start=body.period_start,
        period_end=body.period_end,
        created_by=actor.user.id,
    )
    db.add(plan)
    await db.flush()
    recipients = await plan_event(db, locked, plan, "created")
    await db.commit()
    request.app.state.bus.wake(recipients)
    return await plan_detail(db, plan)


@router.get("/team/{team}/plan/{number}")
async def read_plan(team: str, number: int, actor: ActorDep, db: DB) -> PlanDetail:
    """Return a plan with its rows and what it came to.

    Args:
        team: The Team's slug.
        number: The plan's number.
        actor: The caller.
        db: Database session.

    Raises:
        HTTPException: 404 when there is no such plan in the caller's Teams.
    """
    plan, _ = await plan_for(db, team, number, actor)
    return await plan_detail(db, plan)


@router.post("/team/{team}/plan/{number}/item")
async def add_to_plan(
    request: Request, team: str, number: int, body: PlanAddIn, actor: ActorDep, db: DB
) -> PlanDetail:
    """Add promises and tasks; a promise brings its tasks at any depth (decision 0037).

    Work finished before the plan's period is refused, and a promise does not bring it; work
    finished within the period joins.

    An Assistant adds to a draft only; after approval a human adds, and the work joins found or
    off-plan by the rule.

    Args:
        request: The incoming request.
        team: The Team's slug.
        number: The plan's number.
        body: The numbers to add.
        actor: The caller.
        db: Database session.

    Raises:
        HTTPException: 404 when there is no such plan or task; 403 when the caller may not write
            there, or for an Assistant after approval; 409 ``no_tracker`` without the tracker,
            ``closed`` for a closed plan, ``finished`` for work finished before the period.
    """
    plan, found = await plan_for(db, team, number, actor, write=True)
    if plan.closed_at is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, {"code": "closed", "message": f"«{plan.name}» is closed"}
        )
    if plan.approved_at is not None:
        need_human(actor, "Adding work to an approved plan")
    for task_number in body.tasks:
        task, _ = await task_for(db, team, task_number, actor)
        if await finished_before(db, plan, task):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                {
                    "code": "finished",
                    "message": f"{ref(task.number)} was finished before the plan's period: it has "
                    "nothing to plan",
                },
            )
        for each in [
            task,
            *(await joinable_under(db, plan, task) if task.type == TaskType.Promise else []),
        ]:
            await join(db, actor, plan, each)
    recipients = await plan_event(db, found, plan, "added")
    await db.commit()
    request.app.state.bus.wake(recipients)
    return await plan_detail(db, plan)


@router.delete("/team/{team}/plan/{number}/item/{task_number}")
async def remove_from_plan(
    request: Request, team: str, number: int, task_number: int, actor: ActorDep, db: DB
) -> PlanDetail:
    """Take a task out of a draft: one not started always, a started one only before the period
    begins, a finished one never (decision 0037).

    Args:
        request: The incoming request.
        team: The Team's slug.
        number: The plan's number.
        task_number: The task's number.
        actor: The caller.
        db: Database session.

    Raises:
        HTTPException: 404 when there is no such plan, task or row; 403 when the caller may not
            write there; 409 ``no_tracker`` without the tracker, ``not_draft`` for an approved or
            closed plan, ``finished`` or ``started`` for a task that cannot leave.
    """
    plan, found = await plan_for(db, team, number, actor, write=True)
    task, _ = await task_for(db, team, task_number, actor)
    item = await db.get(PlanItem, (plan.id, task.id))
    if item is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"{ref(task.number)} is not in «{plan.name}»"
        )
    if plan.approved_at is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "code": "not_draft",
                "message": f"«{plan.name}» is approved: its rows stay; postpone the work instead",
            },
        )
    stage = await db.get(Stage, task.stage_id)
    assert stage is not None
    category = CATEGORY[stage.kind]
    if category == Category.Finished:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "code": "finished",
                "message": f"{ref(task.number)} is finished: it stays in the plan",
            },
        )
    if category == Category.InProgress and await today_of(db, plan) >= plan.period_start:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "code": "started",
                "message": f"{ref(task.number)} is under way in the plan's period: it stays; "
                "postpone it instead",
            },
        )
    await db.delete(item)
    record(db, task, "plan_left", actor, {"plan": plan.number, "name": plan.name})
    recipients = await plan_event(db, found, plan, "removed")
    await db.commit()
    request.app.state.bus.wake(recipients)
    return await plan_detail(db, plan)


@router.patch("/team/{team}/plan/{number}/item/{task_number}")
async def change_row(
    request: Request,
    team: str,
    number: int,
    task_number: int,
    body: PlanItemPatch,
    actor: ActorDep,
    db: DB,
) -> PlanDetail:
    """A human corrects a row's mark, names what off-plan work drops, or postpones a row (0037).

    Args:
        request: The incoming request.
        team: The Team's slug.
        number: The plan's number.
        task_number: The task's number.
        body: What changes.
        actor: The human.
        db: Database session.

    Raises:
        HTTPException: 404 when there is no such plan, task or row; 403 for an Assistant or when
            the caller may not write there; 409 ``no_tracker`` without the tracker, ``closed``
            for a closed plan; 422 for a mark before approval or on planned work, or a
            postponement without a reason.
    """
    need_human(actor, "Changing a plan's row")
    plan, found = await plan_for(db, team, number, actor, write=True)
    if plan.closed_at is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, {"code": "closed", "message": f"«{plan.name}» is closed"}
        )
    task, _ = await task_for(db, team, task_number, actor)
    item = await db.get(PlanItem, (plan.id, task.id))
    if item is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"{ref(task.number)} is not in «{plan.name}»"
        )
    if body.mark is not None and body.mark != item.mark:
        if item.mark == PlanMark.Planned:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"{ref(task.number)} is planned; only found and off-plan are corrected",
            )
        record(
            db, task, "plan_mark", actor, {"plan": plan.number, "from": item.mark, "to": body.mark}
        )
        item.mark = PlanMark(body.mark)
    if body.dropped is not None and body.dropped.strip() != item.dropped:
        item.dropped = body.dropped.strip()
        record(db, task, "plan_dropped", actor, {"plan": plan.number, "text": item.dropped})
    if body.postponed is True and item.postponed_at is None:
        reason = (body.reason or "").strip()
        if not reason:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "Say why it is postponed: in favour of which work, or the time misjudged",
            )
        item.postponed_at, item.postponed_by, item.postponed_reason = now(), actor.user.id, reason
        record(db, task, "plan_postponed", actor, {"plan": plan.number, "reason": reason})
    elif body.postponed is False and item.postponed_at is not None:
        item.postponed_at, item.postponed_by, item.postponed_reason = None, None, ""
        record(db, task, "plan_resumed", actor, {"plan": plan.number})
    recipients = await plan_event(db, found, plan, "row")
    await db.commit()
    request.app.state.bus.wake(recipients)
    return await plan_detail(db, plan)


@router.post("/team/{team}/plan/{number}/approve")
async def approve_plan(
    request: Request, team: str, number: int, actor: ActorDep, db: DB
) -> PlanDetail:
    """A human approves a draft: what joins from now on is found or off-plan (0037).

    Args:
        request: The incoming request.
        team: The Team's slug.
        number: The plan's number.
        actor: The human.
        db: Database session.

    Raises:
        HTTPException: 404 when there is no such plan; 403 for an Assistant or when the caller
            may not write there; 409 ``no_tracker`` without the tracker, ``not_draft`` for a plan
            approved already.
    """
    need_human(actor, "Approving a plan")
    plan, found = await plan_for(db, team, number, actor, write=True)
    if plan.approved_at is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {"code": "not_draft", "message": f"«{plan.name}» is approved already"},
        )
    plan.approved_at, plan.approved_by = now(), actor.user.id
    recipients = await plan_event(db, found, plan, "approved")
    await db.commit()
    request.app.state.bus.wake(recipients)
    return await plan_detail(db, plan)


@router.post("/team/{team}/plan/{number}/close")
async def close_plan(
    request: Request, team: str, number: int, actor: ActorDep, db: DB
) -> PlanDetail:
    """A human closes an approved plan after its period; each row's result is fixed (0037).

    Done is Done, or a promise Delivered, by the period's last day; cancelled is Cancelled or
    Withdrawn; the rest is not done. Work finished later does not change it. Days are the Team's,
    in its time zone.

    Args:
        request: The incoming request.
        team: The Team's slug.
        number: The plan's number.
        actor: The human.
        db: Database session.

    Raises:
        HTTPException: 404 when there is no such plan; 403 for an Assistant or when the caller
            may not write there; 409 ``no_tracker`` without the tracker, ``not_approved`` for a
            draft, ``closed`` for a closed plan, ``period`` before the period's end.
    """
    need_human(actor, "Closing a plan")
    plan, found = await plan_for(db, team, number, actor, write=True)
    if plan.closed_at is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, {"code": "closed", "message": f"«{plan.name}» is closed"}
        )
    if plan.approved_at is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {"code": "not_approved", "message": f"«{plan.name}» is a draft: approve it first"},
        )
    zone = await zone_of(db, plan)
    if local_day(now(), zone) <= plan.period_end:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {"code": "period", "message": f"«{plan.name}» runs until {plan.period_end}"},
        )
    for item in await db.scalars(select(PlanItem).where(PlanItem.plan_id == plan.id)):
        task = await db.get(Task, item.task_id)
        assert task is not None
        stage = await db.get(Stage, task.stage_id)
        assert stage is not None
        finished = task.finished_at
        if stage.kind in (StageKind.Cancelled, StageKind.Withdrawn):
            item.result = PlanResult.Cancelled
        elif (
            stage.kind in (StageKind.Done, StageKind.Delivered)
            and finished is not None
            and local_day(finished, zone) <= plan.period_end
        ):
            item.result = PlanResult.Done
        else:
            item.result = PlanResult.NotDone
    plan.closed_at, plan.closed_by = now(), actor.user.id
    recipients = await plan_event(db, found, plan, "closed")
    await db.commit()
    request.app.state.bus.wake(recipients)
    return await plan_detail(db, plan)
