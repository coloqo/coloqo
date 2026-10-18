"""The event stream over Server-Sent Events (decisions 0002, 0006)."""

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select

from coloqo_server.models import Event
from coloqo_server.security import ActorDep

router = APIRouter(tags=["events"])

HEARTBEAT_SECONDS = 15
"""A service event with the last event number goes out this often (decision 0006)."""

REREAD_SECONDS = 5
"""The stream rereads the log this often even without a wake-up."""


def _frame(kind: str, data: dict, event_id: int | None = None) -> str:
    """Format one SSE frame.

    Args:
        kind: Event name.
        data: JSON payload.
        event_id: Id the client reconnects with; heartbeats have none.
    """
    head = f"id: {event_id}\n" if event_id is not None else ""
    return f"{head}event: {kind}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.get("/events")
async def events(
    request: Request,
    actor: ActorDep,
    after: Annotated[int | None, Query(ge=0)] = None,
    last_event_id: Annotated[int | None, Header()] = None,
) -> StreamingResponse:
    """Stream the caller's events; reconnect with the last id to get what was missed.

    Without ``after`` or ``Last-Event-ID`` the stream starts with new events only. The first
    frame is ``ready`` with the current last id; ``heartbeat`` frames repeat it every 15 s.

    Args:
        request: The incoming request.
        actor: The caller.
        after: Send events with a greater id.
        last_event_id: The same, as browsers send it on reconnect.
    """
    database = request.app.state.database
    bus = request.app.state.bus
    user_id = actor.user.id

    async def frames() -> AsyncIterator[str]:
        """Yield frames until the client goes away."""
        async with database.sessions() as db:
            newest = await db.scalar(
                select(func.coalesce(func.max(Event.id), 0)).where(Event.user_id == user_id)
            )
        cursor = last_event_id if last_event_id is not None else after
        if cursor is None:
            cursor = newest
        flag = bus.listen(user_id)
        try:
            yield "retry: 3000\n\n" + _frame("ready", {"last": newest})
            since_heartbeat = 0.0
            while not await request.is_disconnected():
                flag.clear()
                async with database.sessions() as db:
                    rows = list(
                        await db.scalars(
                            select(Event)
                            .where(Event.user_id == user_id, Event.id > cursor)
                            .order_by(Event.id)
                            .limit(200)
                        )
                    )
                for row in rows:
                    yield _frame(row.kind, row.data, row.id)
                    cursor = row.id
                if rows:
                    continue
                started = asyncio.get_running_loop().time()
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(flag.wait(), REREAD_SECONDS)
                since_heartbeat += asyncio.get_running_loop().time() - started
                if since_heartbeat >= HEARTBEAT_SECONDS:
                    since_heartbeat = 0.0
                    yield _frame("heartbeat", {"last": cursor})
        finally:
            bus.forget(user_id, flag)

    return StreamingResponse(
        frames(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
