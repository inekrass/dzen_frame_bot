"""Privacy-safe aggregate usage statistics backed by SQLite."""

from __future__ import annotations

import asyncio
import logging
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from pathlib import Path

logger = logging.getLogger(__name__)


class StatsEvent(StrEnum):
    """Allowed aggregate counter columns."""

    START = "starts"
    UPLOAD_REQUEST = "upload_requests"
    PROFILE_REQUEST = "profile_requests"
    PROCESSED = "processed"
    CENTERED = "centered"
    ERROR = "errors"


@dataclass(frozen=True, slots=True)
class StatsCounters:
    """Counters for one day or an all-time aggregate."""

    starts: int = 0
    upload_requests: int = 0
    profile_requests: int = 0
    processed: int = 0
    centered: int = 0
    errors: int = 0


@dataclass(frozen=True, slots=True)
class StatsSnapshot:
    """Today's counters together with all-time totals."""

    day: date
    today: StatsCounters
    total: StatsCounters


class StatsRepository:
    """Store daily counters without Telegram identifiers or file metadata."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def increment(self, event: StatsEvent, day: date) -> None:
        """Atomically increment one allowed counter for a calendar day."""
        column = event.value
        statement = f"""
            INSERT INTO daily_stats (day, {column})
            VALUES (?, 1)
            ON CONFLICT(day) DO UPDATE SET {column} = {column} + 1
        """
        with closing(self._connect()) as connection, connection:
            connection.execute(statement, (day.isoformat(),))

    def snapshot(self, day: date) -> StatsSnapshot:
        """Read one day's counters and all-time sums."""
        with closing(self._connect()) as connection:
            today_row = connection.execute(
                "SELECT * FROM daily_stats WHERE day = ?",
                (day.isoformat(),),
            ).fetchone()
            total_row = connection.execute(
                """
                SELECT
                    COALESCE(SUM(starts), 0) AS starts,
                    COALESCE(SUM(upload_requests), 0) AS upload_requests,
                    COALESCE(SUM(profile_requests), 0) AS profile_requests,
                    COALESCE(SUM(processed), 0) AS processed,
                    COALESCE(SUM(centered), 0) AS centered,
                    COALESCE(SUM(errors), 0) AS errors
                FROM daily_stats
                """
            ).fetchone()

        return StatsSnapshot(
            day=day,
            today=_counters_from_row(today_row),
            total=_counters_from_row(total_row),
        )

    def _initialize(self) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS daily_stats (
                    day TEXT PRIMARY KEY,
                    starts INTEGER NOT NULL DEFAULT 0 CHECK (starts >= 0),
                    upload_requests INTEGER NOT NULL DEFAULT 0
                        CHECK (upload_requests >= 0),
                    profile_requests INTEGER NOT NULL DEFAULT 0
                        CHECK (profile_requests >= 0),
                    processed INTEGER NOT NULL DEFAULT 0 CHECK (processed >= 0),
                    centered INTEGER NOT NULL DEFAULT 0 CHECK (centered >= 0),
                    errors INTEGER NOT NULL DEFAULT 0 CHECK (errors >= 0)
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path, timeout=10.0)
        connection.row_factory = sqlite3.Row
        return connection


def _counters_from_row(row: sqlite3.Row | None) -> StatsCounters:
    if row is None:
        return StatsCounters()
    return StatsCounters(
        starts=row["starts"],
        upload_requests=row["upload_requests"],
        profile_requests=row["profile_requests"],
        processed=row["processed"],
        centered=row["centered"],
        errors=row["errors"],
    )


class StatsService:
    """Async boundary that prevents metrics failures from breaking the bot."""

    def __init__(self, repository: StatsRepository) -> None:
        self._repository = repository
        self._lock = asyncio.Lock()

    async def record(self, event: StatsEvent) -> None:
        """Record an event, logging but suppressing storage failures."""
        async with self._lock:
            try:
                await asyncio.to_thread(self._repository.increment, event, date.today())
            except sqlite3.Error:
                logger.exception("Statistics update failed")

    async def snapshot(self) -> StatsSnapshot:
        """Return today's and all-time counters."""
        async with self._lock:
            return await asyncio.to_thread(self._repository.snapshot, date.today())
