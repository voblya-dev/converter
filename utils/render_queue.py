"""In-process FIFO render queue."""
from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from dataclasses import dataclass, field
from itertools import count

from config import MAX_PARALLEL_RENDERS, MAX_USER_QUEUE


_global_sem = asyncio.Semaphore(max(1, MAX_PARALLEL_RENDERS))
_queues: dict[int, deque["RenderTicket"]] = defaultdict(deque)
_lock = asyncio.Lock()
_seq = count(1)


class RenderQueueFull(RuntimeError):
    """Raised when a user has too many waiting render jobs."""


@dataclass(eq=False)
class RenderTicket:
    user_id: int
    seq: int = field(default_factory=lambda: next(_seq))
    ready: asyncio.Event = field(default_factory=asyncio.Event)
    _acquired_global: bool = False
    _released: bool = False

    async def __aenter__(self) -> "RenderTicket":
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.release()

    async def release(self) -> None:
        if self._released:
            return
        self._released = True
        if self._acquired_global:
            self._acquired_global = False
            _global_sem.release()
        async with _lock:
            queue = _queues.get(self.user_id)
            if queue:
                try:
                    queue.remove(self)
                except ValueError:
                    pass
                if queue:
                    queue[0].ready.set()
                else:
                    _queues.pop(self.user_id, None)

    async def wait_until_ready(self) -> None:
        while True:
            async with _lock:
                queue = _queues.get(self.user_id)
                if queue and queue[0] is self:
                    break
                if not queue or self not in queue:
                    raise RenderQueueFull("Render ticket is no longer queued")
            await self.ready.wait()
            self.ready.clear()
        await _global_sem.acquire()
        self._acquired_global = True

    async def position(self) -> int:
        async with _lock:
            queue = _queues.get(self.user_id)
            if not queue:
                return 0
            try:
                return list(queue).index(self) + 1
            except ValueError:
                return 0


async def enqueue_render(user_id: int) -> RenderTicket:
    ticket = RenderTicket(user_id=user_id)
    async with _lock:
        queue = _queues[user_id]
        if MAX_USER_QUEUE > 0 and len(queue) >= MAX_USER_QUEUE:
            raise RenderQueueFull("Render queue is full for this user")
        queue.append(ticket)
        if len(queue) == 1:
            ticket.ready.set()
    return ticket


class render_slot:
    """Compatibility wrapper for code that only needs a render slot."""

    def __init__(self, user_id: int):
        self.user_id = user_id
        self.ticket: RenderTicket | None = None

    async def __aenter__(self):
        self.ticket = await enqueue_render(self.user_id)
        await self.ticket.wait_until_ready()
        return self.ticket

    async def __aexit__(self, exc_type, exc, tb):
        if self.ticket:
            await self.ticket.release()
