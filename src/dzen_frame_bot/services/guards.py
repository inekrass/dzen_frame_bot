"""Short-lived in-memory guards without user photo persistence."""

from __future__ import annotations

import asyncio
import time


class AlbumGuard:
    """Suppress duplicate rejection messages for one Telegram media group."""

    def __init__(self, ttl_seconds: float = 60.0) -> None:
        self._ttl_seconds = ttl_seconds
        self._seen_at: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def should_notify(self, media_group_id: str) -> bool:
        """Return true once per media group during the configured TTL."""
        now = time.monotonic()
        async with self._lock:
            self._seen_at = {
                group_id: seen_at
                for group_id, seen_at in self._seen_at.items()
                if now - seen_at < self._ttl_seconds
            }
            if media_group_id in self._seen_at:
                return False
            self._seen_at[media_group_id] = now
            return True


class UserRequestGuard:
    """Allow only one active photo operation per Telegram user."""

    def __init__(self) -> None:
        self._active_users: set[int] = set()
        self._lock = asyncio.Lock()

    async def try_acquire(self, user_id: int) -> bool:
        """Acquire the user slot without waiting, or report that it is busy."""
        async with self._lock:
            if user_id in self._active_users:
                return False
            self._active_users.add(user_id)
            return True

    async def release(self, user_id: int) -> None:
        """Release a user slot after success or failure."""
        async with self._lock:
            self._active_users.discard(user_id)
