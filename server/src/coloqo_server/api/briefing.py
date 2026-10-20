"""What a starting session learns: who it is, the rules, its Topics, updates (decisions 0021,
0023, 0024, 0027)."""

from datetime import timedelta

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from coloqo_server.api.topics import ref
from coloqo_server.models import Assistant, Message, MessageKind, Team, Topic, TopicStatus
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

LEGACY_UPDATE = (
    "Coloqo: this session's plugin is older than 0.5.0, and the next release of Coloqo stops "
    "answering it. Update it now: run `claude plugin marketplace update coloqo` and `claude "
    "plugin update coloqo@coloqo` in the shell, then tell your user in one line that the new "
    "version works from the next session."
)


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

    Args:
        db: Database session.
        actor: The session's Assistant.
        team: The linked Team.
        idle_days: Days without Messages before an open Topic is closed.
    """
    assert actor.assistant is not None and actor.project is not None
    rows = (
        await db.execute(
            select(Topic, Assistant)
            .join(Assistant, Assistant.id == Topic.holder_assistant_id)
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
    mine = [topic for topic, holder in rows if holder.id == actor.assistant.id]
    others = [(topic, holder) for topic, holder in rows if holder.id != actor.assistant.id]
    lines: list[str] = []
    if mine:
        lines.append("You hold — continue there and note each stage:")
        for topic in mine[:10]:
            closes = (topic.updated_at + timedelta(days=idle_days)).date()
            lines.append(
                f"- {ref(topic.number)} «{topic.title}»"
                + (f" [{topic.issue}]" if topic.issue else "")
                + f", closes for inactivity on {closes} if quiet"
            )
    else:
        lines.append("You hold no Topic: open one when you take a task, as above.")
    if others:
        lines.append(
            "Held by other sessions of this project — to continue one, take it over with "
            "hold_topic; if its task is done, take it over and close it with the outcome:"
        )
        for topic, holder in others[:10]:
            stage = await last_stage(db, topic)
            lines.append(
                f"- {ref(topic.number)} «{topic.title}»"
                + (f" [{topic.issue}]" if topic.issue else "")
                + f" held by «{holder.name}»"
                + (
                    f", last stage «{stage.body}» on {stage.created_at:%Y-%m-%d %H:%M} UTC"
                    if stage
                    else f", no stage noted, last active {topic.updated_at:%Y-%m-%d %H:%M} UTC"
                )
            )
    return lines


@router.get("/briefing", response_model=Briefing)
async def briefing(request: Request, actor: ActorDep, db: DB) -> Briefing | JSONResponse:
    """Tell a starting session who it is in Coloqo and how to work; the server keeps the rules.

    A rule changes here, for every project and Team, without a plugin release. A plugin older
    than 0.5.0 gets the former shape and is told to update (decision 0025).

    Args:
        request: The incoming request.
        actor: The Assistant of the session.
        db: Database session.

    Raises:
        HTTPException: 403 without an Assistant.
    """
    if actor.assistant is None or actor.project is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only an Assistant gets a briefing")
    if actor.legacy:
        from coloqo_server.api.legacy import legacy_briefing

        return JSONResponse(await legacy_briefing(request, db, actor))
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
        RULES.format(
            team=team.name,
            user=actor.user.pseudonym,
            other="globex" if team.slug != "globex" else "acme",
            url=settings.public_url,
            slug=team.slug,
        ),
        "",
        *await held_lines(db, actor, team, settings.idle_close_days),
    ]
    if hint:
        lines += ["", hint]
    return Briefing(text="\n".join(lines), team=team.slug, team_name=team.name)
