"""The event stream over Server-Sent Events (decisions 0002, 0006, 0028)."""

import asyncio
import contextlib
import json
import re
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Header, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from coloqo_server.api.teams import find_team
from coloqo_server.models import Event, Member, Team
from coloqo_server.security import ActorDep, pushed_teams, require_reader

router = APIRouter(tags=["events"])

HEARTBEAT_SECONDS = 15
"""A service event with the cursor goes out this often (decision 0006)."""

REREAD_SECONDS = 5
"""The stream rereads the log this often even without a wake-up."""


CURSOR_PART = re.compile(r"([a-z0-9-]{1,40}):([0-9]{1,15})")
"""One Team's part of a cursor: its slug and the number of the last event sent."""


def _frame(kind: str, data: dict, cursor: str | None = None) -> str:
    """Format one SSE frame.

    Args:
        kind: Event name.
        data: JSON payload.
        cursor: What the client reconnects with; service frames have none.
    """
    head = f"id: {cursor}\n" if cursor is not None else ""
    return f"{head}event: {kind}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def read_cursor(text: str | None) -> dict[str, int]:
    """Return the event numbers a cursor names by Team slug (decision 0028).

    A cursor reads ``acme:120,globex:45``. Parts of another form are left out, as the database
    ids that servers before 0.7.0 sent: their Teams start from the current number.

    Args:
        text: The cursor the client sent.
    """
    parts: dict[str, int] = {}
    for part in (text or "").split(","):
        match = CURSOR_PART.fullmatch(part.strip())
        if match:
            parts[match[1]] = int(match[2])
    return parts


def write_cursor(cursor: dict[int, int], slugs: dict[int, str]) -> str:
    """Return a cursor naming each Team by its slug, in the order of the slugs.

    Args:
        cursor: The last event number sent, by Team id.
        slugs: The Teams' slugs, by id.
    """
    return ",".join(
        f"{slugs[team]}:{number}"
        for team, number in sorted(cursor.items(), key=lambda item: slugs[item[0]])
    )


def shaped(data: dict, legacy: bool) -> dict:
    """Return an event's data in the shape its reader knows (decision 0025).

    Events keep both shapes: the data of decision 0025, and under ``legacy`` the former one
    with database ids, for plugins older than 0.5.0.

    Args:
        data: The stored data.
        legacy: The reader is a plugin older than 0.5.0.
    """
    if legacy:
        return data.get("legacy", {})
    return {key: value for key, value in data.items() if key != "legacy"}


@router.get("/events")
async def events(
    request: Request,
    actor: ActorDep,
    after: str | None = None,
    last_event_id: Annotated[str | None, Header()] = None,
) -> StreamingResponse:
    """Stream the events of the caller's Teams; reconnect with the cursor to get what was missed.

    Events are numbered per Team, and every frame's id is the cursor naming the last number
    sent of each Team: ``acme:120,globex:45`` (decision 0028). A Team the cursor does not name
    starts from its current number: without ``after`` or ``Last-Event-ID``, or a Team joined
    since; a Team left is dropped. The first frame is ``ready`` with the cursor; ``heartbeat``
    frames repeat it every 15 s. An Assistant gets only the events of the Team its project is
    linked to; an unlinked one gets the service frames alone (decision 0020).

    Args:
        request: The incoming request.
        actor: The caller.
        after: The cursor to start after.
        last_event_id: The same, as browsers send it on reconnect.

    Raises:
        HTTPException: 403 for a plugin request without an Assistant.
    """
    require_reader(actor)
    database = request.app.state.database
    bus = request.app.state.bus
    user_id = actor.user.id
    scope = pushed_teams(actor)
    legacy = actor.legacy

    async def teams_now(db: AsyncSession) -> dict[int, tuple[str, int]]:
        """Return the Teams whose events the stream carries now: slug and last number by id.

        Args:
            db: Database session.
        """
        rows = await db.execute(
            select(Team.id, Team.slug, Team.last_event)
            .join(Member, Member.team_id == Team.id)
            .where(Member.user_id == user_id)
        )
        return {team: (slug, last) for team, slug, last in rows if scope is None or team in scope}

    async def frames() -> AsyncIterator[str]:
        """Yield frames until the client goes away."""
        cursor: dict[int, int] = {}
        async with database.sessions() as db:
            teams = await teams_now(db)
            asked = read_cursor(last_event_id if last_event_id is not None else after)
            for slug, number in asked.items():
                team = await find_team(db, slug)
                if team is not None and team.id in teams:
                    # A number past the Team's last would wait for events that already came.
                    cursor[team.id] = min(number, teams[team.id][1])
        cursor = {team: cursor.get(team, last) for team, (_, last) in teams.items()}
        slugs = {team: slug for team, (slug, _) in teams.items()}
        flag = bus.listen(user_id)
        try:
            yield "retry: 3000\n\n" + _frame("ready", {"last": write_cursor(cursor, slugs)})
            since_heartbeat = 0.0
            while not await request.is_disconnected():
                flag.clear()
                async with database.sessions() as db:
                    teams = await teams_now(db)
                    cursor = {team: cursor.get(team, last) for team, (_, last) in teams.items()}
                    slugs = {team: slug for team, (slug, _) in teams.items()}
                    rows = (
                        list(
                            await db.scalars(
                                select(Event)
                                .where(
                                    or_(
                                        *(
                                            and_(Event.team_id == team, Event.number > number)
                                            for team, number in cursor.items()
                                        )
                                    )
                                )
                                .order_by(Event.id)
                                .limit(200)
                            )
                        )
                        if cursor
                        else []
                    )
                for row in rows:
                    cursor[row.team_id] = max(cursor[row.team_id], row.number)
                    data = shaped(row.data, legacy)
                    if data:
                        yield _frame(row.kind, data, write_cursor(cursor, slugs))
                if rows:
                    continue
                started = asyncio.get_running_loop().time()
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(flag.wait(), REREAD_SECONDS)
                since_heartbeat += asyncio.get_running_loop().time() - started
                if since_heartbeat >= HEARTBEAT_SECONDS:
                    since_heartbeat = 0.0
                    yield _frame("heartbeat", {"last": write_cursor(cursor, slugs)})
        finally:
            bus.forget(user_id, flag)

    return StreamingResponse(
        frames(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
