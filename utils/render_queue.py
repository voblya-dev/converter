"""Small in-process render queue limits."""
from __future__ import annotations

import asyncio
from collections import defaultdict

from config import MAX_PARALLEL_RENDERS, MAX_USER_QUEUE


_global_sem = asyncio.Semaphore(max(1, MAX_PARALLEL_RENDERS))
_user_active: dict[int, int] = defaultdict(int)
_lock = asyncio.Lock()


class RenderQueueFull(RuntimeError):
    """Raised when a user already has too many active render jobs."""


class render_slot:
    def __init__(self, user_id: int):
        self.user_id = user_id

    async def __aenter__(self):
        async with _lock:
            if _user_active[self.user_id] >= max(1, MAX_USER_QUEUE):
                raise RenderQueueFull("Render queue is full for this user")
            _user_active[self.user_id] += 1
        try:
            await _global_sem.acquire()
        except Exception:
            async with _lock:
                _user_active[self.user_id] -= 1
            raise
        return self

    async def __aexit__(self, exc_type, exc, tb):
        _global_sem.release()
        async with _lock:
            _user_active[self.user_id] -= 1
            if _user_active[self.user_id] <= 0:
                _user_active.pop(self.user_id, None)
