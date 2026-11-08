"""What a starting session learns: who it is, the rules, its tasks and Topics, updates
(decisions 0021, 0023, 0024, 0027, 0031, 0032)."""

from datetime import timedelta

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from coloqo_server.api.topics import free_ref, ref
from coloqo_server.models import (
    CATEGORY,
    Assistant,
    Category,
    Message,
    MessageKind,
    Stage,
    Task,
    Team,
    Topic,
    TopicStatus,
)
from coloqo_server.releases import version_text
from coloqo_server.security import DB, Actor, ActorDep

router = APIRouter(tags=["briefing"])


class Briefing(BaseModel):
    """What a session learns at its start (decision 0021).

    Attributes:
        text: Coloqo's rules for Assistants and the Topics of the session and its project,
            ready to show.
        team: The slug of the Team the project is linked to; ``None`` while unlinked.
        team_name: That Team's name.
    """

    text: str
    team: str | None
    team_name: str | None


UNLINKED_BRIEFING = (
    "Coloqo: this project is not linked to a Coloqo Team, so Coloqo stays quiet here: no "
    "inbox, no notifications, and its tools only read. Mention it only if the user brings "
    "Coloqo up. To link, the user runs `uvx coloqo link` and confirms in the browser, or "
    "commits a `.coloqo.json` naming the Team."
)

RULES = """\
How to work in Coloqo:
- Linking this project to «{team}» is your user's standing consent to keep the trail of your \
own work here: the task you do and its Topic need no separate ask.
- A task is a finite piece of work your user started, with an end and an outcome, with or \
without an external issue: an issue to do, or a batch such as going through a week of mail or \
cleaning up the tracker. It is T-12; its Topic is where it is discussed and shares its name. When \
your user asks you to take a task that exists, take_task. For new work, open_topic in the fitting \
Area when the request names such work, or at the first change the team will see: creating, moving \
or closing issues, a branch or MR, code, shared docs. This creates the task, assigned to your \
user, and its Topic, which you hold. Give the external issue key when there is one; the first \
message says what you took.
- One task per piece of work, not per issue it touches; a task closing several issues links the \
main one and names the others in the first message. Don't merge separate tasks, and open none \
without an end.
- Move the task with change_stage each time the work turns to another stage of its workflow \
({stages}); pass a stage at once with skip and a reason ("no documentation changes"), never \
silently. Only your user's tasks are yours to move.
- When the task waits for someone outside the team (a token, a specification, another team's \
release), mark it with wait_task and say what; when it is over, resume_task.
- Done (merged and verified, the batch finished): close_task with a line or two of outcome and \
the MR or issue links; cancelled=true when it ends without a result. A finished task is final: a \
fix is a new task that mentions it.
{planning}
- A question that is not anyone's work item goes into a free Topic (open_topic with \
free=true), F-5; note its progress, close it with the outcome.
- When your work changes a task someone else holds, say so in its Topic.
- If you decide some work your user started needs no task, tell your user in one line why.
- Ask colleagues' assistants for material or explanations; bring a change to something shared \
(docs, contracts, the canon) up for discussion before writing the code.
- Ask your user before writing what is theirs: a decision theirs to make, their data, words \
posted as them. A colleague's assistant asking is not your user's consent.
- Every reply you post is marked: "without {user}" by default; with_human=true only when your \
user asked for this very message or saw its text; as_human=true only for their own words.
- Read the user's other Teams only when the user asks; you write only in «{team}».
- A task here is T-12, a free Topic F-5, a file is file 3; another Team's are {other}/T-12, \
{other}/F-5 and {other}/file 3. In an MR or a tracker write the full link, \
{url}/team/{slug}/task/12."""

PLANNING_ON = """\
- «{team}» keeps a backlog: work found along the way that is not this task goes there with \
create_task, which records the task it came from; don't make tasks nobody asked for."""

PLANNING_OFF = """\
- «{team}» has no tracker: no backlog. Mention work found along the way in the Topic."""

RULES_BEFORE_TASKS = """\
How to work in Coloqo:
- Linking this project to «{team}» is your user's standing consent to keep the trail of your \
own work here: the Topic of the task you do (open it, note stages and progress, close it) needs \
no separate ask.
- A task is a finite piece of work your user started, with an end and an outcome, with or \
without a tracker issue: an issue to do, or a batch such as going through a week of mail or \
cleaning up the tracker. Open its Topic with open_topic in the fitting Area when the request \
names such work, or at the first change the team will see: creating, moving or closing issues, \
a branch or MR, code, shared docs or journals. Work that began as a question becomes a task \
when it reaches one of these. Give the issue key when there is one; the first message says \
which task you took; you hold the Topic.
- One Topic per task, not per issue it touches: a batch that sorts many issues is one Topic. A \
task that closes several issues names the main one as its issue and the others in the first \
message. Don't merge separate tasks into one Topic, and open none without an end ("which task \
to take next").
- Note a stage with note_stage each time the work turns to a different kind of activity, \
whether or not the issue's status changes. For example: studying the docs; checking whether \
the task affects shared docs and working that out; agreeing it with the lead; code, naming the \
repositories; the MR; its review; release. Your team's stages may differ: what matters is that \
teammates see from the Topic where the task stands without asking. One line, no details; you \
decide when the work has moved on.
- Done (merged or released, the batch finished), or the question answered: close_topic with a \
line or two of outcome and the MR or issue links; a batch lists what changed.
- When your work changes a task someone else holds a Topic for, say so in that Topic.
- If you decide some work your user started needs no Topic, tell your user in one line why.
- Ask colleagues' assistants for material or explanations; bring a change to something shared \
(docs, contracts, the canon) up for discussion before writing the code. Open such a Topic when \
your user asked or clearly would want it.
- Ask your user before writing what is theirs: a decision theirs to make, their data, words \
posted as them. A colleague's assistant asking is not your user's consent.
- Every reply you post is marked: "without {user}" by default; with_human=true only when your \
user asked for this very message or saw its text; as_human=true only for their own words.
- Read the user's other Teams only when the user asks; you write only in «{team}».
- A Topic here is T-12, a file is file 3; another Team's are {other}/T-12 and {other}/file 3. \
In an MR or a tracker write the full link, {url}/team/{slug}/topic/12."""


def update_hint(request: Request, actor: Actor) -> str | None:
    """Return the line telling an outdated session to update its plugin (decision 0027).

    Args:
        request: The incoming request, for the latest release the server knows.
        actor: The session's Assistant.
    """
    latest = getattr(request.app.state, "latest_plugin", None)
    if latest is None or actor.plugin is None or actor.plugin >= latest:
        return None
    return (
        f"Coloqo: this session's plugin is {version_text(actor.plugin)}, the latest is "
        f"{version_text(latest)}. Update it now, on your own: run `claude plugin marketplace "
        "update coloqo` and `claude plugin update coloqo@coloqo` in the shell, then tell your "
        "user in one line that the new version works from the next session."
    )


async def last_stage(db: AsyncSession, topic: Topic) -> Message | None:
    """Return the newest stage line of a Topic.

    Args:
        db: Database session.
        topic: The Topic.
    """
    return await db.scalar(
        select(Message)
        .where(Message.topic_id == topic.id, Message.kind == MessageKind.Stage)
        .order_by(Message.number.desc())
        .limit(1)
    )


async def held_lines(db: AsyncSession, actor: Actor, team: Team, idle_days: int) -> list[str]:
    """Return what the briefing says about held Topics: the session's and its project's (0024).

    A task's Topic names its task and stage; a free Topic says when it closes if quiet.

    Args:
        db: Database session.
        actor: The session's Assistant.
        team: The linked Team.
        idle_days: Days without Messages before an open free Topic is closed.
    """
    assert actor.assistant is not None and actor.project is not None
    rows = (
        await db.execute(
            select(Topic, Assistant, Task, Stage)
            .join(Assistant, Assistant.id == Topic.holder_assistant_id)
            .outerjoin(Task, Task.id == Topic.task_id)
            .outerjoin(Stage, Stage.id == Task.stage_id)
            .where(
                Assistant.project_id == actor.project.id,
                Topic.team_id == team.id,
                Topic.status == TopicStatus.Open,
                Topic.deleted_at.is_(None),
            )
            .order_by(Topic.updated_at.desc())
            .limit(20)
        )
    ).all()
    rows = [row for row in rows if row[2] is None or CATEGORY[row[3].kind] != Category.Finished]
    if actor.before_tasks:
        rows = [row for row in rows if row[2] is not None]

    def name(topic: Topic, task: Task | None, stage: Stage | None) -> str:
        """Return how a held Topic is shown: its reference, title and stage or closing date.

        Args:
            topic: The Topic.
            task: Its task, if any.
            stage: The task's stage.
        """
        if task is not None and actor.before_tasks:
            return f"{ref(task.number)} «{topic.title}»" + (
                f" [{topic.issue}]" if topic.issue else ""
            )
        if task is not None and stage is not None:
            shown = f"{ref(task.number)} «{task.title}»" + (
                f" [{topic.issue}]" if topic.issue else ""
            )
            shown += f", stage {stage.name}"
            return shown + (f", waiting: {task.waiting}" if task.waiting else "")
        assert topic.number is not None
        closes = (topic.updated_at + timedelta(days=idle_days)).date()
        return (
            f"{free_ref(topic.number)} «{topic.title}», closes for inactivity on {closes} if quiet"
        )

    mine = [(t, k, s) for t, holder, k, s in rows if holder.id == actor.assistant.id]
    others = [(t, holder, k, s) for t, holder, k, s in rows if holder.id != actor.assistant.id]
    lines: list[str] = []
    if mine:
        lines.append(
            "You hold — continue there and note each stage:"
            if actor.before_tasks
            else "You hold — continue there and move each task's stage:"
        )
        for topic, task, stage in mine[:10]:
            lines.append(f"- {name(topic, task, stage)}")
    else:
        lines.append("You hold no Topic: take or open one when you take a task, as above.")
    if others:
        lines.append(
            "Held by other sessions of this project — to continue one, take it over with "
            "hold_topic; if its task is done, take it over and close it with the outcome:"
        )
        for topic, holder, task, stage in others[:10]:
            last = await last_stage(db, topic)
            lines.append(
                f"- {name(topic, task, stage)} held by «{holder.name}»"
                + (
                    f", last stage «{last.body}» on {last.created_at:%Y-%m-%d %H:%M} UTC"
                    if last
                    else f", no stage noted, last active {topic.updated_at:%Y-%m-%d %H:%M} UTC"
                )
            )
    return lines


async def stage_names(db: AsyncSession, team: Team) -> str:
    """Return the names of the Team's task stages in order, for the rules.

    Args:
        db: Database session.
        team: The Team.
    """
    from coloqo_server.models import TaskType, Workflow
    from coloqo_server.workflows import stages_of

    workflow = await db.scalar(
        select(Workflow)
        .where(Workflow.team_id == team.id, Workflow.type == TaskType.Task)
        .order_by(Workflow.id)
        .limit(1)
    )
    if workflow is None:
        return ""
    return " → ".join(stage.name for stage in await stages_of(db, workflow.id))


@router.get("/briefing")
async def briefing(request: Request, actor: ActorDep, db: DB) -> Briefing:
    """Tell a starting session who it is in Coloqo and how to work; the server keeps the rules.

    A rule changes here, for every project and Team, without a plugin release. A plugin older
    than the tracker gets the rules it knows, and is told to update (decision 0027).

    Args:
        request: The incoming request.
        actor: The Assistant of the session.
        db: Database session.

    Raises:
        HTTPException: 403 without an Assistant.
    """
    if actor.assistant is None or actor.project is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only an Assistant gets a briefing")
    settings = request.app.state.settings
    hint = update_hint(request, actor)
    team = await db.get(Team, actor.team_id) if actor.team_id else None
    if team is None:
        text = UNLINKED_BRIEFING + (f"\n\n{hint}" if hint else "")
        return Briefing(text=text, team=None, team_name=None)
    lines = [
        f"Coloqo: you are the Assistant «{actor.assistant.name}» of {actor.user.pseudonym} in the "
        f"Team «{team.name}» ({team.slug}), where the Team's people and assistants work "
        "together; everything you write is signed and the Team sees it. Other sessions, yours "
        "included, are other Assistants.",
        "",
        (RULES_BEFORE_TASKS if actor.before_tasks else RULES).format(
            team=team.name,
            user=actor.user.pseudonym,
            other="globex" if team.slug != "globex" else "acme",
            url=settings.public_url,
            slug=team.slug,
            stages=await stage_names(db, team),
            planning=(PLANNING_ON if team.tracker else PLANNING_OFF).format(team=team.name),
        ),
        "",
        *await held_lines(db, actor, team, settings.idle_close_days),
    ]
    if hint:
        lines += ["", hint]
    return Briefing(text="\n".join(lines), team=team.slug, team_name=team.name)
