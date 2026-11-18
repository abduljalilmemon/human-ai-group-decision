"""Session engine: one asyncio task per session walks the phases, sleeping until each deadline.

The transition rule (next_phase) and the run loop (run_session) take no I/O of their own, so tests
can drive them with fakes. SessionEngine wires them to the database and the WebSocket fan-out.
"""
import asyncio
import logging
from typing import Awaitable, Callable

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .config import Experiment
from .lobby import LiveSession
from .models import Event, ExperimentSession
from .protocol import now_ms

log = logging.getLogger(__name__)

WAITING, DISCUSSION, VOTING, ROUND_RESULT, FINAL = (
    "WAITING", "DISCUSSION", "VOTING", "ROUND_RESULT", "FINAL",
)

Step = tuple[str, int, float | None]  # (phase, round, duration in seconds; None = no deadline)
Hook = Callable[[LiveSession], Awaitable[None]]


def next_phase(phase: str, round_: int, exp: Experiment) -> Step:
    """Pure transition rule for section 7.2 of PLAN.md."""
    if phase == WAITING or phase == ROUND_RESULT:
        return DISCUSSION, round_ + 1, exp.discussion_seconds
    if phase == DISCUSSION:
        return VOTING, round_, exp.voting_seconds
    if phase == VOTING:
        if round_ >= exp.rounds:
            return FINAL, round_, None
        if exp.show_round_results:
            return ROUND_RESULT, round_, exp.results_pause_seconds
        return DISCUSSION, round_ + 1, exp.discussion_seconds
    raise ValueError(f"no transition from {phase}")


async def run_session(
    session: LiveSession,
    exp: Experiment,
    *,
    persist: Hook,
    broadcast: Hook,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    clock: Callable[[], int] = now_ms,
) -> None:
    """Advance the session from its current phase to FINAL, recording and broadcasting each change."""
    while session.phase != FINAL:
        phase, round_, duration = next_phase(session.phase, session.round, exp)
        session.phase, session.round = phase, round_
        session.phase_ends_at = None if duration is None else clock() + int(duration * 1000)
        await persist(session)
        await broadcast(session)
        if session.phase_ends_at is not None:
            # Sleep to the absolute deadline so slow DB writes or sends do not stretch a phase.
            await sleep(max(0, session.phase_ends_at - clock()) / 1000)


class SessionEngine:
    def __init__(self, exp: Experiment, db: async_sessionmaker[AsyncSession], broadcast: Hook):
        self._exp = exp
        self._db = db
        self._broadcast = broadcast
        self._tasks: set[asyncio.Task] = set()

    async def start(self, session: LiveSession) -> None:
        """Lobby callback: run this session's phases in the background."""
        task = asyncio.create_task(
            run_session(session, self._exp, persist=self._persist, broadcast=self._broadcast)
        )
        self._tasks.add(task)
        task.add_done_callback(self._task_done)

    async def shutdown(self) -> None:
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)

    async def _persist(self, session: LiveSession) -> None:
        async with self._db() as db:
            db.add(Event(
                session_id=session.id,
                type="phase_change",
                payload={"phase": session.phase, "round": session.round, "ends_at": session.phase_ends_at},
            ))
            if session.phase == FINAL:
                row = await db.get(ExperimentSession, session.id)
                row.status = "finished"
                row.ended_at = func.now()
            await db.commit()

    def _task_done(self, task: asyncio.Task) -> None:
        self._tasks.discard(task)
        if not task.cancelled() and task.exception():
            log.error("Session engine failed", exc_info=task.exception())
