"""Agent interface and the per-seat driver that applies the blind-condition defences.

An Agent only decides *what* to say or whom to vote for. AgentSeat decides *whether* and *when*:
it reacts to phase changes and new messages, applies human-like delays and caps, and sends
through the same submit_chat()/submit_vote() callables the engine uses for humans.
"""
import asyncio
import logging
import random
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Coroutine

from ..protocol import now_ms

log = logging.getLogger(__name__)

# Phase names, duplicated from engine.py to avoid a circular import.
DISCUSSION, VOTING = "DISCUSSION", "VOTING"

MAX_LINES_PER_ROUND = 3
REPLY_CHANCE = 0.6  # chance of answering a message from someone else
MENTIONED_REPLY_CHANCE = 0.9  # higher when the message names this seat
OPENER_CHANCE = 0.7  # chance of speaking first in a round
MAX_AGENT_CHARS = 220

# Typing model for reply_delay(): reading time plus time to type the text.
READ_SECONDS = (1.5, 4.0)
SECONDS_PER_CHAR = 0.09
TYPE_JITTER = (0.8, 1.3)
MIN_REPLY_SECONDS, MAX_REPLY_SECONDS = 2.0, 14.0

# Phrases that would reveal an AI. Matched case-insensitively on whole words.
_TELLS = re.compile(
    r"\b(ai|a\.i\.|bots?|chat ?bot|language model|llm|artificial intelligence|assistant|"
    r"claude|anthropic|openai|gpt|machine learning|programmed|my training|as a model)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ChatLine:
    round: int
    label: str
    text: str


@dataclass(frozen=True)
class AgentView:
    """What an agent may know: its own label, the public labels and the public chat."""
    me: str
    players: list[str]
    round: int
    transcript: list[ChatLine]

    @property
    def others(self) -> list[str]:
        return [p for p in self.players if p != self.me]


class Agent(ABC):
    @abstractmethod
    async def reply(self, view: AgentView) -> str | None:
        """Next chat line, or None to stay quiet."""

    @abstractmethod
    async def vote(self, view: AgentView) -> str:
        """A label from view.players."""


# --- Pure blind-defence rules (unit-tested) --------------------------------------------------

def has_tell(text: str) -> bool:
    return bool(_TELLS.search(text))


def clean_reply(text: str | None, me: str) -> str | None:
    """Normalise an agent's line; None if it is empty, too long or reveals an AI."""
    if not text:
        return None
    line = " ".join(text.split())
    if line.lower().startswith(me.lower() + ":"):
        line = line[len(me) + 1:].strip()  # model echoed the transcript format
    line = line.strip('"').strip()
    if not line or len(line) > MAX_AGENT_CHARS or has_tell(line):
        return None
    return line


def reply_delay(text: str, rng: random.Random) -> float:
    """Seconds from deciding to reply until the line is sent: read, then type at a human pace."""
    read = rng.uniform(*READ_SECONDS)
    typing = len(text) * SECONDS_PER_CHAR * rng.uniform(*TYPE_JITTER)
    return min(MAX_REPLY_SECONDS, max(MIN_REPLY_SECONDS, read + typing))


def vote_delay(remaining_seconds: float, rng: random.Random) -> float:
    """Random point in the first two thirds of the voting window, so the vote always lands in time."""
    return rng.uniform(0.25, 0.65) * max(0.0, remaining_seconds)


# --- Per-seat driver ------------------------------------------------------------------------

SubmitChat = Callable[[Any, Any, str], Awaitable[str | None]]  # (session, seat, text) -> error
SubmitVote = Callable[[Any, Any, str], Awaitable[str | None]]  # (session, seat, target) -> error


@dataclass
class AgentSeat:
    agent: Agent
    seat: Any  # lobby.Seat
    session: Any  # lobby.LiveSession
    transcript: list[ChatLine]  # shared with the other agent seats of this session
    submit_chat: SubmitChat
    submit_vote: SubmitVote
    rng: random.Random
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep
    clock: Callable[[], int] = now_ms
    sent: dict[int, int] = field(default_factory=dict)  # round -> lines sent or pending
    _tasks: set[asyncio.Task] = field(default_factory=set)
    _pending: asyncio.Task | None = None  # one pending reply at a time

    # Events from the engine. Both are synchronous and never raise.

    def on_phase(self) -> None:
        self.cancel()
        phase = self.session.phase
        if phase == DISCUSSION and self.rng.random() < OPENER_CHANCE:
            self._start_reply(first_wait=self.rng.uniform(2.0, 8.0))
        elif phase == VOTING:
            self._spawn(self._vote(self._key()))

    def on_message(self, line: ChatLine) -> None:
        if line.label == self.seat.label or self.session.phase != DISCUSSION:
            return
        named = mentions(line.text, self.seat.label)
        if self.rng.random() < (MENTIONED_REPLY_CHANCE if named else REPLY_CHANCE):
            self._start_reply(first_wait=0.0)

    def cancel(self) -> None:
        for task in self._tasks:
            task.cancel()
        self._tasks.clear()
        self._pending = None

    # Internals

    def _start_reply(self, first_wait: float) -> None:
        round_ = self.session.round
        busy = self._pending is not None and not self._pending.done()
        if busy or self.sent.get(round_, 0) >= MAX_LINES_PER_ROUND:
            return
        if self._remaining_s() < first_wait + MIN_REPLY_SECONDS + 1:
            return  # too late in the round to type anything
        self.sent[round_] = self.sent.get(round_, 0) + 1  # counted now, so the cap holds while a reply is pending
        self._pending = self._spawn(self._reply(first_wait, self._key()))

    async def _reply(self, first_wait: float, key: tuple[str, int]) -> None:
        if first_wait:
            await self.sleep(first_wait)
        started = self.clock()
        text = clean_reply(await self.agent.reply(self._view()), self.seat.label)
        if text is None:
            return
        # The delay counts from the decision, so generation time is part of it, not added to it.
        elapsed = (self.clock() - started) / 1000
        await self.sleep(max(0.0, reply_delay(text, self.rng) - elapsed))
        if self._key() == key:  # never act outside the phase it was triggered in
            await self.submit_chat(self.session, self.seat, text)

    async def _vote(self, key: tuple[str, int]) -> None:
        remaining = self._remaining_s()
        target_s = vote_delay(remaining, self.rng)
        started = self.clock()
        view = self._view()
        try:
            # Leave at least a second before the deadline whatever the agent does.
            choice = await asyncio.wait_for(self.agent.vote(view), timeout=max(0.1, remaining - 1.0))
        except Exception:
            log.warning("agent vote failed; using a random choice", exc_info=True)
            choice = None
        if choice not in view.players:
            choice = self.rng.choice(view.others)
        await self.sleep(max(0.0, target_s - (self.clock() - started) / 1000))
        if self._key() == key:
            await self.submit_vote(self.session, self.seat, choice)

    def _key(self) -> tuple[str, int]:
        return self.session.phase, self.session.round

    def _view(self) -> AgentView:
        return AgentView(
            me=self.seat.label,
            players=sorted(self.session.labels),
            round=self.session.round,
            transcript=list(self.transcript),
        )

    def _remaining_s(self) -> float:
        ends = self.session.phase_ends_at
        return 0.0 if ends is None else max(0.0, (ends - self.clock()) / 1000)

    def _spawn(self, coro: Coroutine[Any, Any, None]) -> asyncio.Task:
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._task_done)
        return task

    def _task_done(self, task: asyncio.Task) -> None:
        self._tasks.discard(task)
        if not task.cancelled() and task.exception():
            # An agent failure is logged and dropped; it never reaches the session engine.
            log.error("agent task failed", exc_info=task.exception())


class SessionAgents:
    """All AI seats of one session, sharing one transcript."""

    def __init__(self, seats: list[AgentSeat], transcript: list[ChatLine]):
        self.seats = seats
        self.transcript = transcript

    def on_phase(self) -> None:
        for s in self.seats:
            _safely(s.on_phase)

    def on_message(self, round_: int, label: str, text: str) -> None:
        line = ChatLine(round_, label, text)
        self.transcript.append(line)
        for s in self.seats:
            _safely(s.on_message, line)

    def close(self) -> None:
        for s in self.seats:
            s.cancel()


def mentions(text: str, label: str) -> bool:
    """True if text names this label, e.g. 'Player B', 'player b' or a bare 'B'."""
    letter = label.split()[-1]
    return bool(
        re.search(rf"\b{re.escape(label)}\b", text, re.IGNORECASE)
        or re.search(rf"(?<![\w']){re.escape(letter)}(?![\w'])", text)
    )


def _safely(fn: Callable[..., None], *args: Any) -> None:
    try:
        fn(*args)
    except Exception:
        log.error("agent event handler failed", exc_info=True)
