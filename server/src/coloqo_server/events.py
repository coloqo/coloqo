"""The event log and its wake-ups (decisions 0006, 0008, 0028).

Events are rows in the database, one per event of a Team, numbered in the Team; the stream of
a User reads its Teams' events past the numbers in its cursor. A process wakes its
own streams when it commits events. The cloud runs one process (decision 0008), so this
replaces ``LISTEN/NOTIFY`` until there is a second one; a stream also rereads the log every
few seconds, so nothing is lost if a wake-up is.
"""

import asyncio
from collections import defaultdict
from collections.abc import Iterable

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from coloqo_server.models import Event, Member, Team


class EventBus:
    """Wakes the streams of Users who got new events."""

    def __init__(self) -> None:
        """Start with no listeners."""
        self._listeners: defaultdict[int, set[asyncio.Event]] = defaultdict(set)

    def listen(self, user_id: int) -> asyncio.Event:
        """Return a flag that is set when the User gets events.

        Args:
            user_id: Whose events to wait for.
        """
        flag = asyncio.Event()
        self._listeners[user_id].add(flag)
        return flag

    def forget(self, user_id: int, flag: asyncio.Event) -> None:
        """Stop setting a flag returned by ``listen``.

        Args:
            user_id: Whose events it waited for.
            flag: The flag.
        """
        self._listeners[user_id].discard(flag)
        if not self._listeners[user_id]:
            del self._listeners[user_id]

    def wake(self, user_ids: Iterable[int]) -> None:
        """Set the flags of the given Users' streams; call after the events are committed.

        Args:
            user_ids: Users who got events.
        """
        for user_id in set(user_ids):
            for flag in self._listeners.get(user_id, ()):
                flag.set()


async def add_event(db: AsyncSession, team_id: int, kind: str, data: dict) -> set[int]:
    """Add a Team's event with its next number; commit, then ``EventBus.wake`` the result.

    Taking the number locks the Team's row until the commit, so a Team's events commit in the
    order of their numbers and a stream past number N never skips one committed later.

    Args:
        db: Database session of the change the event describes.
        team_id: The Team.
        kind: Event kind.
        data: What a client needs to decide whether to read more.

    Returns:
        The Team's Members, whose streams to wake.

    Raises:
        sqlalchemy.exc.SQLAlchemyError: The database refused the change.
    """
    number = await db.scalar(
        update(Team)
        .where(Team.id == team_id)
        .values(last_event=Team.last_event + 1)
        .returning(Team.last_event)
    )
    db.add(Event(team_id=team_id, number=number, kind=kind, data=data))
    return set(await db.scalars(select(Member.user_id).where(Member.team_id == team_id)))
