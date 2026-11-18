"""Session engine: one asyncio task per session walks the phases, sleeping until each deadline.

The transition rule (next_phase), the run loop (run_session) and the chat path (submit_chat) take no
I/O of their own, so tests can drive them with fakes. SessionEngine wires them to the database and
the WebSocket fan-out.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .config import Experiment
from . import protocol
from .lobby import LiveSession, Seat
from .models import Event, ExperimentSession, Message
from .protocol import Payload, now_ms

log = logging.getLogger(__name__)

WAITING, DISCUSSION, VOTING, ROUND_RESULT, FINAL = (
    "WAITING", "DISCUSSION", "VOTING", "ROUND_RESULT", "FINAL",
)

Step = tuple[str, int, float | None]  # (phase, round, duration in seconds; None = no deadline)
Hook = Callable[[LiveSession], Awaitable[None]]
SendAll = Callable[[LiveSession, Payload], Awaitable[None]]
# (session_id, participant_id, round, text, sent_at ms) -> new message id
SaveMessage = Callable[[int, int, int, str, int], Awaitable[int]]

MAX_CHAT_CHARS = 500


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


def check_chat(phase: str, text: Any) -> tuple[str | None, str | None]:
    """Pure chat rules. Returns (clean text, None) if accepted, or (None, error reason)."""
    if phase != DISCUSSION:
        return None, "chat_closed"
    if not isinstance(text, str):
        return None, "invalid_message"
    clean = text.strip()
    if not clean:
        return None, "empty_message"
    if len(clean) > MAX_CHAT_CHARS:
        return None, "message_too_long"
    return clean, None


async def submit_chat(
    session: LiveSession,
    seat: Seat,
    text: Any,
    *,
    save: SaveMessage,
    send_all: SendAll,
    clock: Callable[[], int] = now_ms,
) -> str | None:
    """The single chat path for every participant. Returns an error reason, or None once sent."""
    clean, reason = check_chat(session.phase, text)
    if reason:
        return reason
    round_, sent_at = session.round, clock()  # read before any await so a phase change cannot shift them
    message_id = await save(session.id, seat.participant_id, round_, clean, sent_at)
    await send_all(session, protocol.message(message_id, seat.label, clean, sent_at))
    return None


class SessionEngine:
    def __init__(
        self,
        exp: Experiment,
        db: async_sessionmaker[AsyncSession],
        broadcast: Hook,
        send_all: SendAll,
    ):
        self._exp = exp
        self._db = db
        self._broadcast = broadcast
        self._send_all = send_all
        self._tasks: set[asyncio.Task] = set()

    async def start(self, session: LiveSession) -> None:
        """Lobby callback: run this session's phases in the background."""
        task = asyncio.create_task(
            run_session(session, self._exp, persist=self._persist, broadcast=self._broadcast)
        )
        self._tasks.add(task)
        task.add_done_callback(self._task_done)

    async def submit_chat(self, session: LiveSession, seat: Seat, text: Any) -> str | None:
        return await submit_chat(session, seat, text, save=self._save_message, send_all=self._send_all)

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

    async def _save_message(self, session_id: int, participant_id: int, round_: int, text: str, sent_at: int) -> int:
        async with self._db() as db:
            row = Message(
                session_id=session_id,
                participant_id=participant_id,
                round=round_,
                text=text,
                created_at=datetime.fromtimestamp(sent_at / 1000, tz=timezone.utc),
            )
            db.add(row)
            await db.commit()
            return row.id

    def _task_done(self, task: asyncio.Task) -> None:
        self._tasks.discard(task)
        if not task.cancelled() and task.exception():
            log.error("Session engine failed", exc_info=task.exception())
