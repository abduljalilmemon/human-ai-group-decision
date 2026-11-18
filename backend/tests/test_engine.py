import asyncio

import pytest

from app.config import Experiment
from app.engine import DISCUSSION, FINAL, ROUND_RESULT, VOTING, WAITING, next_phase, run_session
from app.lobby import LiveSession, Seat


def exp(**overrides) -> Experiment:
    values = dict(
        discussion_seconds=10, voting_seconds=5, results_pause_seconds=3, min_wait_seconds=(0.1, 0.2)
    )
    return Experiment(**(values | overrides))


def walk(e: Experiment) -> list[tuple]:
    steps, phase, round_ = [], WAITING, 0
    while phase != FINAL:
        phase, round_, duration = next_phase(phase, round_, e)
        steps.append((phase, round_, duration))
    return steps


def test_full_sequence():
    assert walk(exp()) == [
        (DISCUSSION, 1, 10),
        (VOTING, 1, 5),
        (ROUND_RESULT, 1, 3),
        (DISCUSSION, 2, 10),
        (VOTING, 2, 5),
        (FINAL, 2, None),
    ]


def test_round_result_can_be_skipped():
    phases = [p for p, _, _ in walk(exp(show_round_results=False))]
    assert phases == [DISCUSSION, VOTING, DISCUSSION, VOTING, FINAL]


def test_final_is_terminal():
    with pytest.raises(ValueError):
        next_phase(FINAL, 2, exp())


class FakeClock:
    """Time only moves when the engine sleeps, so deadlines are exact."""

    def __init__(self):
        self.now = 1_000_000
        self.sleeps: list[float] = []

    def __call__(self) -> int:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += int(seconds * 1000)


def test_run_session_persists_and_broadcasts_each_phase_once():
    session = LiveSession(id=1, labels=["Player A", "Player B", "Player C"], human_slots=1)
    session.seats.append(Seat(label="Player A", kind="human", participant_id=1, token="t"))
    clock = FakeClock()
    persisted, broadcast = [], []

    async def persist(s):
        persisted.append((s.phase, s.round, s.phase_ends_at))

    async def send(s):
        broadcast.append((s.phase, s.round, s.phase_ends_at))

    asyncio.run(run_session(session, exp(), persist=persist, broadcast=send, sleep=clock.sleep, clock=clock))

    assert persisted == broadcast  # every recorded change is also sent, in the same order
    assert [(p, r) for p, r, _ in persisted] == [
        (DISCUSSION, 1), (VOTING, 1), (ROUND_RESULT, 1), (DISCUSSION, 2), (VOTING, 2), (FINAL, 2),
    ]
    assert clock.sleeps == [10, 5, 3, 10, 5]  # one sleep per timed phase, none after FINAL
    # Each deadline is the previous one plus the phase duration (no drift).
    assert persisted[1][2] - persisted[0][2] == 5_000
    assert persisted[-1][2] is None
    assert session.phase == FINAL
