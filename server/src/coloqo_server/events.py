"""The event log and its wake-ups (decisions 0006, 0008).

Events are rows in the database; the stream of a User reads them by id. A process wakes its
own streams when it commits events. The cloud runs one process (decision 0008), so this
replaces ``LISTEN/NOTIFY`` until there is a second one; a stream also rereads the log every
few seconds, so nothing is lost if a wake-up is.
"""

import asyncio
from collections import defaultdict
from collections.abc import Iterable

from sqlalchemy.ext.asyncio import AsyncSession

from coloqo_server.models import Event


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


def add_events(db: AsyncSession, user_ids: Iterable[int], kind: str, data: dict) -> set[int]:
    """Add one event per User to the session; commit, then ``EventBus.wake`` the result.

    Args:
        db: Database session of the change the events describe.
        user_ids: Recipients.
        kind: Event kind.
        data: What a client needs to decide whether to read more.
    """
    recipients = set(user_ids)
    db.add_all(Event(user_id=user_id, kind=kind, data=data) for user_id in recipients)
    return recipients
