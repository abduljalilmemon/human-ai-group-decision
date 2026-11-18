"""Session engine: one asyncio task per session walks the phases, sleeping until each deadline.

The transition rule (next_phase), the run loop (run_session), the chat path (submit_chat) and the
voting path (submit_vote, close_voting) take no I/O of their own, so tests can drive them with fakes. SessionEngine wires them to the database and
the WebSocket fan-out.
"""
import asyncio
import logging
import random
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .config import Experiment
from . import protocol, voting
from .agents import AgentFactory
from .agents.base import AgentSeat, SessionAgents
from .lobby import ChatRecord, LiveSession, Seat
from .models import Event, ExperimentSession, Message, Vote
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
SendOne = Callable[[LiveSession, Seat], Awaitable[None]]
# (session_id, round, [(voter participant_id, target participant_id or None = abstain)])
SaveVotes = Callable[[int, int, list[tuple[int, int | None]]], Awaitable[None]]
# (session_id, decision maker participant_id, tie_break, tallies_by_round)
SaveDecision = Callable[[int, int, str, dict[int, dict[str, int]]], Awaitable[None]]

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
    end_voting: Hook | None = None,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    clock: Callable[[], int] = now_ms,
) -> None:
    """Advance the session from its current phase to FINAL, recording and broadcasting each change.

    A phase ends at its deadline, or earlier once session.phase_over is set (all ballots in).
    """
    while session.phase != FINAL:
        phase, round_, duration = next_phase(session.phase, session.round, exp)
        session.phase_over.clear()
        session.phase, session.round = phase, round_
        session.phase_ends_at = None if duration is None else clock() + int(duration * 1000)
        await persist(session)
        await broadcast(session)
        if session.phase_ends_at is not None:
            # Sleep to the absolute deadline so slow DB writes or sends do not stretch a phase.
            await _first_of(sleep(max(0, session.phase_ends_at - clock()) / 1000), session.phase_over)
        if session.phase == VOTING and end_voting is not None:
            await end_voting(session)


async def _first_of(sleeper: Awaitable[None], wake: asyncio.Event) -> None:
    """Return when the sleep finishes or the event is set, whichever comes first."""
    tasks = {asyncio.ensure_future(sleeper), asyncio.ensure_future(wake.wait())}
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in tasks:
            task.cancel()


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
    session.chat.append(ChatRecord(message_id, seat.label, clean, sent_at))  # for replay on reconnect
    await send_all(session, protocol.message(message_id, seat.label, clean, sent_at))
    return None


async def submit_vote(
    session: LiveSession,
    seat: Seat,
    target: Any,
    *,
    save: SaveVotes,
    send_state: SendOne,
) -> str | None:
    """The single vote path for every participant. Returns an error reason, or None once recorded."""
    round_ = session.round
    ballots = session.ballots.setdefault(round_, {})
    reason = voting.check_vote(session.phase, target, session.labels, seat.label in ballots)
    if reason:
        return reason
    ballots[seat.label] = target  # recorded before any await, so a concurrent duplicate is rejected
    ids = {s.label: s.participant_id for s in session.seats}
    await save(session.id, round_, [(seat.participant_id, ids[target])])
    await send_state(session, seat)  # confirms has_voted to the voter only
    # End early once every seat has voted, but only if the save did not outlast this voting phase.
    if session.phase == VOTING and session.round == round_ and len(ballots) == len(session.seats):
        session.phase_over.set()
    return None


async def close_voting(
    session: LiveSession,
    exp: Experiment,
    *,
    save: SaveVotes,
    save_decision: SaveDecision,
    send_all: SendAll,
    rng: voting.Chooser | None = None,
) -> None:
    """End a voting phase: missing ballots become abstentions, then the tally or final result is sent."""
    round_ = session.round
    ballots = session.ballots.setdefault(round_, {})
    missing = [s for s in session.seats if s.label not in ballots]
    for s in missing:
        ballots[s.label] = None  # before any await, so a late vote is rejected as a duplicate
    if missing:
        await save(session.id, round_, [(s.participant_id, None) for s in missing])

    # Sorted, never session.labels: that order is humans first, AI last, so it would leak seat type.
    labels = sorted(session.labels)
    tallies = {r: voting.tally(b.values(), labels) for r, b in sorted(session.ballots.items())}
    if round_ < exp.rounds:
        if exp.show_round_results:
            session.shown_tallies[round_] = tallies[round_]
            await send_all(session, protocol.round_result(round_, tallies[round_]))
        return
    earlier = tallies.get(round_ - 1, voting.tally([], labels))
    winner, tie_break = voting.decide_winner(tallies[round_], earlier, rng)
    ids = {s.label: s.participant_id for s in session.seats}
    await save_decision(session.id, ids[winner], tie_break, tallies)
    session.final = (winner, tallies, tie_break)
    await send_all(session, protocol.final_result(winner, tallies, tie_break))


class SessionEngine:
    def __init__(
        self,
        exp: Experiment,
        db: async_sessionmaker[AsyncSession],
        broadcast: Hook,
        send_all: SendAll,
        send_state: SendOne,
        make_agent: AgentFactory | None = None,
        rng: random.Random | None = None,
    ):
        self._exp = exp
        self._make_agent = make_agent
        self._agents: dict[int, SessionAgents] = {}  # session id -> its AI seats
        self._db = db
        self._broadcast = broadcast
        self._send_all = send_all
        self._send_state = send_state
        self._rng = rng or random.Random()
        self._tasks: set[asyncio.Task] = set()

    async def start(self, session: LiveSession) -> None:
        """Lobby callback: run this session's phases in the background."""
        self._agents[session.id] = self._seat_agents(session)
        task = asyncio.create_task(
            run_session(
                session, self._exp, persist=self._persist, broadcast=self._on_phase, end_voting=self._close_voting
            )
        )
        self._tasks.add(task)
        task.add_done_callback(lambda t: self._task_done(t, session.id))

    async def submit_chat(self, session: LiveSession, seat: Seat, text: Any) -> str | None:
        """Used by humans (ws.py) and AI seats alike."""
        round_ = session.round
        reason = await submit_chat(session, seat, text, save=self._save_message, send_all=self._send_all)
        if reason is None and session.id in self._agents:
            self._agents[session.id].on_message(round_, seat.label, text.strip())
        return reason

    async def submit_vote(self, session: LiveSession, seat: Seat, target: Any) -> str | None:
        return await submit_vote(session, seat, target, save=self._save_votes, send_state=self._send_state)

    async def _close_voting(self, session: LiveSession) -> None:
        await close_voting(
            session, self._exp, save=self._save_votes, save_decision=self._save_decision,
            send_all=self._send_all, rng=self._rng,
        )

    def _seat_agents(self, session: LiveSession) -> SessionAgents:
        transcript: list = []
        used_lines: set[str] = set()
        seats = [
            AgentSeat(
                agent=self._make_agent(used_lines), seat=seat, session=session, transcript=transcript,
                submit_chat=self.submit_chat, submit_vote=self.submit_vote, rng=self._rng,
            )
            for seat in session.seats
            if seat.kind == "ai" and self._make_agent is not None
        ]
        return SessionAgents(seats, transcript)

    async def _on_phase(self, session: LiveSession) -> None:
        """Broadcast the new phase to humans first, then let the AI seats react to it."""
        await self._broadcast(session)
        agents = self._agents.get(session.id)
        if agents is None:
            return
        if session.phase == FINAL:
            self._agents.pop(session.id).close()
        else:
            agents.on_phase()

    async def shutdown(self) -> None:
        for agents in self._agents.values():
            agents.close()
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

    async def _save_votes(self, session_id: int, round_: int, votes: list[tuple[int, int | None]]) -> None:
        async with self._db() as db:
            db.add_all(
                Vote(session_id=session_id, round=round_, voter_id=voter, target_id=target) for voter, target in votes
            )
            await db.commit()

    async def _save_decision(
        self, session_id: int, winner_id: int, tie_break: str, tallies: dict[int, dict[str, int]]
    ) -> None:
        async with self._db() as db:
            row = await db.get(ExperimentSession, session_id)
            row.decision_maker_id = winner_id
            row.tie_break = tie_break
            # Research record of how the outcome was reached, including any random draw.
            db.add(Event(
                session_id=session_id,
                type="decision",
                payload={
                    "decision_maker_id": winner_id,
                    "tie_break": tie_break,
                    "tallies_by_round": {str(r): t for r, t in tallies.items()},
                },
            ))
            await db.commit()

    def _task_done(self, task: asyncio.Task, session_id: int) -> None:
        self._tasks.discard(task)
        agents = self._agents.pop(session_id, None)
        if agents is not None:  # session ended abnormally: stop its agents too
            agents.close()
        if not task.cancelled() and task.exception():
            log.error("Session engine failed", exc_info=task.exception())
