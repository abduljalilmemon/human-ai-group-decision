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


@dataclass(frozen=True)
class ChatRecord:
    """A chat line already broadcast, kept so a reconnecting client can be replayed the history."""
    id: int
    label: str
    text: str
    sent_at: int  # epoch ms


@dataclass
class LiveSession:
    id: int
    labels: list[str]  # shuffled per session; humans take them in arrival order, AI the rest
    human_slots: int
    seats: list[Seat] = field(default_factory=list)
    phase: str = "WAITING"
    round: int = 0
    phase_ends_at: int | None = None  # epoch ms; None while waiting
    # round -> voter label -> target label (None = abstained). Secret: never sent to clients.
    ballots: dict[int, dict[str, str | None]] = field(default_factory=dict)
    phase_over: asyncio.Event = field(default_factory=asyncio.Event)  # set to end a phase early
    # What clients have already been shown, for replay on reconnect (see protocol.replay).
    chat: list[ChatRecord] = field(default_factory=list)
    shown_tallies: dict[int, dict[str, int]] = field(default_factory=dict)  # round -> anonymous tally
    final: tuple[str, dict[int, dict[str, int]], str] | None = None  # (winner, tallies_by_round, tie_break)

    def free_labels(self) -> list[str]:
        """Unseated labels in shuffled order. A released waiting-room seat can leave a gap anywhere."""
        taken = {s.label for s in self.seats}
        return [label for label in self.labels if label not in taken]

    def has_voted(self, label: str) -> bool:
        return self.ballots.get(self.round, {}).get(label) is not None

    @property
    def humans_full(self) -> bool:
        return sum(s.kind == "human" for s in self.seats) >= self.human_slots


OnStart = Callable[[LiveSession], Awaitable[None]]

# A human who leaves the open waiting room keeps their seat this long, so a refresh does not lose it.
RELEASE_GRACE_SECONDS = 10.0


class Lobby:
    def __init__(
        self,
        settings: Config,
        db: async_sessionmaker[AsyncSession],
        on_start: OnStart,
        rng: random.Random | None = None,
        grace_seconds: float = RELEASE_GRACE_SECONDS,
    ):
        self._settings = settings
        self._grace = grace_seconds
        self._db = db
        self._on_start = on_start
        self._rng = rng or random.Random()
        self._lock = asyncio.Lock()  # serialises joins so two callers never take the same seat
        self._open: LiveSession | None = None
        self._by_token: dict[str, tuple[LiveSession, Seat]] = {}
        self._sockets: dict[str, int] = {}  # token -> number of open WebSockets
        self._tasks: set[asyncio.Task] = set()

    def find(self, token: str) -> tuple[LiveSession, Seat] | None:
        return self._by_token.get(token)

    def connected(self, token: str) -> None:
        self._sockets[token] = self._sockets.get(token, 0) + 1

    def disconnected(self, token: str) -> None:
        """Called when a socket closes. Only an open waiting room releases seats; after that a
        missing human simply abstains, so a session never stalls or loses a seat once it is starting."""
        count = self._sockets.get(token, 0) - 1
        if count > 0:
            self._sockets[token] = count
            return
        self._sockets.pop(token, None)
        found = self._by_token.get(token)
        if found is not None and found[0] is self._open:
            self._spawn(self._release_after_grace(token))

    async def _release_after_grace(self, token: str) -> None:
        await asyncio.sleep(self._grace)
        async with self._lock:  # same lock as join, so a release never races a seat assignment
            found = self._by_token.get(token)
            if found is None or self._sockets.get(token) or found[0] is not self._open:
                return  # reconnected (e.g. a refresh), or the session filled up meanwhile
            session, seat = found
            del self._by_token[token]  # from here on the token is unknown to the WebSocket endpoint
            session.seats.remove(seat)
            async with self._db() as db:
                row = await db.get(Participant, seat.participant_id)
                if row is not None:
                    await db.delete(row)
                db.add(Event(session_id=session.id, type="seat_released", payload={"label": seat.label}))
                await db.commit()

    async def join(self) -> str:
        """Seat a new human in the open session (opening one if needed) and return their token."""
        async with self._lock:
            if self._open is None:
                self._open = await self._create_session()
            session = self._open
            label = session.free_labels()[0]
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
                for label in session.free_labels()
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
            log.error("Lobby task failed", exc_info=task.exception())
