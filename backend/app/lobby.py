"""Waiting room and matchmaking: fills the human slots of one open session at a time."""
import asyncio
import logging
import random
import secrets
from dataclasses import dataclass, field
from typing import Awaitable, Callable

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .config import Config
from .models import Event, ExperimentSession, Participant

log = logging.getLogger(__name__)


@dataclass
class Seat:
    label: str
    kind: str  # "human" | "ai". Internal only: protocol.py never reads it.
    participant_id: int
    token: str | None = None  # None for AI seats


@dataclass
class LiveSession:
    id: int
    labels: list[str]  # shuffled per session; humans take them in arrival order, AI the rest
    human_slots: int
    seats: list[Seat] = field(default_factory=list)
    phase: str = "WAITING"
    round: int = 0
    phase_ends_at: int | None = None  # epoch ms; None while waiting

    @property
    def humans_full(self) -> bool:
        return sum(s.kind == "human" for s in self.seats) >= self.human_slots


OnStart = Callable[[LiveSession], Awaitable[None]]


class Lobby:
    def __init__(
        self,
        settings: Config,
        db: async_sessionmaker[AsyncSession],
        on_start: OnStart,
        rng: random.Random | None = None,
    ):
        self._settings = settings
        self._db = db
        self._on_start = on_start
        self._rng = rng or random.Random()
        self._lock = asyncio.Lock()  # serialises joins so two callers never take the same seat
        self._open: LiveSession | None = None
        self._by_token: dict[str, tuple[LiveSession, Seat]] = {}
        self._tasks: set[asyncio.Task] = set()

    def find(self, token: str) -> tuple[LiveSession, Seat] | None:
        return self._by_token.get(token)

    async def join(self) -> str:
        """Seat a new human in the open session (opening one if needed) and return their token."""
        async with self._lock:
            if self._open is None:
                self._open = await self._create_session()
            session = self._open
            label = session.labels[len(session.seats)]
            token = secrets.token_urlsafe(32)
            async with self._db() as db:
                row = Participant(session_id=session.id, label=label, kind="human", token=token)
                db.add(row)
                await db.commit()
            seat = Seat(label=label, kind="human", participant_id=row.id, token=token)
            session.seats.append(seat)
            self._by_token[token] = (session, seat)

            if session.humans_full:
                self._open = None  # later joiners get a fresh waiting room
                self._spawn(self._start_after_delay(session))
            return token

    async def shutdown(self) -> None:
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)

    async def _create_session(self) -> LiveSession:
        s = self._settings
        async with self._db() as db:
            row = ExperimentSession(
                status="waiting", condition=s.condition, config_snapshot=s.model_dump(mode="json")
            )
            db.add(row)
            await db.commit()
        labels = self._rng.sample(s.labels, len(s.labels))
        return LiveSession(id=row.id, labels=labels, human_slots=s.human_slots)

    async def _start_after_delay(self, session: LiveSession) -> None:
        # Applied in every condition, so a lone human with two AI partners still waits a
        # plausible amount of time. The client sees no change until the session starts.
        lo, hi = self._settings.experiment.min_wait_seconds
        await asyncio.sleep(self._rng.uniform(lo, hi))

        async with self._db() as db:
            ai_rows = [
                Participant(session_id=session.id, label=label, kind="ai", token=None)
                for label in session.labels[len(session.seats):]
            ]
            db.add_all(ai_rows)
            await db.flush()
            row = await db.get(ExperimentSession, session.id)
            row.status = "running"
            row.started_at = func.now()
            seats = {s.label: s.kind for s in session.seats} | {r.label: "ai" for r in ai_rows}
            db.add(Event(session_id=session.id, type="session_started", payload={"seats": seats}))
            await db.commit()
        session.seats += [Seat(label=r.label, kind="ai", participant_id=r.id) for r in ai_rows]
        await self._on_start(session)  # the engine takes over from WAITING

    def _spawn(self, coro: Awaitable[None]) -> None:
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._task_done)

    def _task_done(self, task: asyncio.Task) -> None:
        self._tasks.discard(task)
        if not task.cancelled() and task.exception():
            log.error("Session start failed", exc_info=task.exception())
