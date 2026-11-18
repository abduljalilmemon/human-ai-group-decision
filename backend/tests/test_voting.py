"""Tally, tie-break and the vote path (submit_vote / close_voting) with fake I/O hooks."""
import asyncio
import random

import pytest

from app.config import Experiment
from app.engine import DISCUSSION, FINAL, ROUND_RESULT, VOTING, close_voting, run_session, submit_vote
from app.lobby import LiveSession, Seat
from app.voting import check_vote, decide_winner, tally

A, B, C = "Player A", "Player B", "Player C"
LABELS = [A, B, C]


class FixedChoice:
    """Injectable random source: always picks the given index of the (sorted) tied labels."""

    def __init__(self, index: int):
        self.index = index
        self.seen: list[list[str]] = []

    def choice(self, seq):
        self.seen.append(list(seq))
        return seq[self.index]


# --- tally -----------------------------------------------------------------------------------------

def test_tally_counts_every_label_and_skips_abstentions():
    assert tally([A, A, None], LABELS) == {A: 2, B: 0, C: 0}


def test_tally_of_no_ballots_is_all_zero():
    assert tally([], LABELS) == {A: 0, B: 0, C: 0}
    assert tally([None, None, None], LABELS) == {A: 0, B: 0, C: 0}


# --- decide_winner ---------------------------------------------------------------------------------

def test_clear_majority():
    assert decide_winner({A: 0, B: 2, C: 1}, {A: 3, B: 0, C: 0}) == (B, "none")


def test_single_vote_with_abstentions_wins_outright():
    r2 = tally([C, None, None], LABELS)
    assert decide_winner(r2, tally([None] * 3, LABELS)) == (C, "none")


def test_tie_resolved_by_round1():
    # A and C tie in round 2; C had more round-1 votes. B led round 1 but is not in the tie.
    assert decide_winner({A: 1, B: 0, C: 1}, {A: 0, B: 2, C: 1}) == (C, "round1")


def test_tie_resolved_by_draw_among_tied_only():
    rng = FixedChoice(1)
    assert decide_winner({A: 1, B: 1, C: 0}, {A: 1, B: 1, C: 1}, rng) == (B, "random")
    assert rng.seen == [[A, B]]  # C was not tied in round 2, so it is not in the draw


def test_three_way_tie_with_abstentions_goes_to_draw():
    r2 = tally([A, B, C], LABELS)
    r1 = tally([A, B, None], LABELS)  # A and B lead round 1, still tied
    rng = FixedChoice(0)
    assert decide_winner(r2, r1, rng) == (A, "random")
    assert rng.seen == [[A, B]]


def test_nobody_voting_at_all_is_a_draw_over_everyone():
    zero = tally([None] * 3, LABELS)
    rng = FixedChoice(2)
    assert decide_winner(zero, zero, rng) == (C, "random")
    assert rng.seen == [LABELS]


def test_draw_is_deterministic_with_a_seeded_source():
    zero = tally([], LABELS)
    picks = {decide_winner(zero, zero, random.Random(42))[0] for _ in range(5)}
    assert len(picks) == 1


# --- check_vote ------------------------------------------------------------------------------------

@pytest.mark.parametrize("phase", ["WAITING", DISCUSSION, ROUND_RESULT, FINAL])
def test_vote_rejected_outside_voting(phase):
    assert check_vote(phase, A, LABELS, already_voted=False) == "voting_closed"


@pytest.mark.parametrize("target", [None, "", "Player D", 1, ["Player A"], {"label": A}])
def test_invalid_target_rejected(target):
    assert check_vote(VOTING, target, LABELS, already_voted=False) == "invalid_target"


def test_duplicate_rejected_and_self_vote_allowed():
    assert check_vote(VOTING, A, LABELS, already_voted=True) == "already_voted"
    assert check_vote(VOTING, A, LABELS, already_voted=False) is None


# --- submit_vote and close_voting (engine paths, fake I/O) ----------------------------------------

class Recorder:
    def __init__(self):
        self.votes: list[tuple] = []
        self.decisions: list[tuple] = []
        self.sent: list[dict] = []
        self.states: list[str] = []

    async def save(self, session_id, round_, votes):
        self.votes += [(session_id, round_, voter, target) for voter, target in votes]

    async def save_decision(self, session_id, winner_id, tie_break, tallies):
        self.decisions.append((session_id, winner_id, tie_break, tallies))

    async def send_all(self, session, payload):
        self.sent.append(payload)

    async def send_state(self, session, seat):
        self.states.append(seat.label)


def make_session(phase=VOTING, round_=1) -> LiveSession:
    s = LiveSession(id=5, labels=[B, C, A], human_slots=2, phase=phase, round=round_)
    s.seats = [
        Seat(label=B, kind="human", participant_id=11, token="tb"),
        Seat(label=C, kind="human", participant_id=12, token="tc"),
        Seat(label=A, kind="ai", participant_id=13),
    ]
    return s


def vote(session, seat_index, target, rec):
    return asyncio.run(
        submit_vote(session, session.seats[seat_index], target, save=rec.save, send_state=rec.send_state)
    )


def close(session, rec, rng=None):
    asyncio.run(close_voting(session, exp(), save=rec.save, save_decision=rec.save_decision,
                             send_all=rec.send_all, rng=rng))


def exp(**overrides) -> Experiment:
    values = dict(discussion_seconds=10, voting_seconds=5, results_pause_seconds=3, min_wait_seconds=(0.1, 0.2))
    return Experiment(**(values | overrides))


def test_vote_is_saved_and_confirmed_to_voter_only():
    s, rec = make_session(), Recorder()
    assert vote(s, 0, B, rec) is None  # self-vote
    assert rec.votes == [(5, 1, 11, 11)]
    assert rec.states == [B] and rec.sent == []
    assert s.has_voted(B) and not s.has_voted(C)


def test_second_vote_in_same_round_rejected_and_not_stored():
    s, rec = make_session(), Recorder()
    vote(s, 0, A, rec)
    assert vote(s, 0, C, rec) == "already_voted"
    assert rec.votes == [(5, 1, 11, 13)]


def test_vote_outside_voting_or_invalid_target_not_stored():
    rec = Recorder()
    assert vote(make_session(DISCUSSION), 0, A, rec) == "voting_closed"
    assert vote(make_session(), 0, "Player Z", rec) == "invalid_target"
    assert rec.votes == [] and rec.states == []


def test_same_voter_may_vote_again_next_round():
    s, rec = make_session(), Recorder()
    vote(s, 0, A, rec)
    s.round = 2
    assert vote(s, 0, A, rec) is None


def test_all_ballots_in_ends_phase_early():
    s, rec = make_session(), Recorder()
    vote(s, 0, A, rec)
    vote(s, 1, A, rec)
    assert not s.phase_over.is_set()
    vote(s, 2, C, rec)
    assert s.phase_over.is_set()


def test_round1_close_stores_abstentions_and_sends_anonymous_tally():
    s, rec = make_session(), Recorder()
    vote(s, 0, C, rec)
    close(s, rec)
    assert sorted(rec.votes) == [(5, 1, 11, 12), (5, 1, 12, None), (5, 1, 13, None)]
    assert rec.sent == [{"type": "round_result", "round": 1, "tallies": {A: 0, B: 0, C: 1}}]
    # Key order is alphabetical, not the seat order (humans first, AI last), which would leak type.
    assert list(rec.sent[0]["tallies"]) == [A, B, C]
    assert rec.decisions == []
    # A late vote after closing is rejected and nothing more is stored.
    assert vote(s, 1, C, rec) == "already_voted"
    assert len(rec.votes) == 3


def test_round_result_skipped_when_disabled():
    s, rec = make_session(), Recorder()
    asyncio.run(close_voting(s, exp(show_round_results=False), save=rec.save,
                             save_decision=rec.save_decision, send_all=rec.send_all))
    assert rec.sent == []


def test_final_close_saves_decision_and_sends_final_result():
    s, rec = make_session(), Recorder()
    vote(s, 0, B, rec)  # round 1: B 1, A 1
    vote(s, 1, A, rec)
    close(s, rec)
    s.round, rec.sent = 2, []
    vote(s, 0, B, rec)  # round 2: B 1, A 1, C abstains -> tie, B and A level in round 1 -> draw
    vote(s, 2, A, rec)
    close(s, rec, rng=FixedChoice(1))  # sorted tie [A, B] -> B
    tallies = {1: {A: 1, B: 1, C: 0}, 2: {A: 1, B: 1, C: 0}}
    assert rec.decisions == [(5, 11, "random", tallies)]
    assert [list(t) for t in rec.sent[0]["tallies_by_round"].values()] == [[A, B, C], [A, B, C]]
    assert rec.sent == [{
        "type": "final_result",
        "decision_maker": B,
        "tallies_by_round": {"1": tallies[1], "2": tallies[2]},
        "tie_break": "random",
    }]


def test_nobody_votes_in_any_round_still_finishes():
    s, rec = make_session(), Recorder()
    close(s, rec)
    s.round = 2
    close(s, rec, rng=FixedChoice(0))
    assert len(rec.votes) == 6 and all(target is None for *_, target in rec.votes)
    assert rec.decisions[0][2] == "random"
    assert rec.sent[-1]["decision_maker"] == A  # sorted [A, B, C], index 0


def test_run_session_ends_voting_early_and_closes_each_round():
    """With a sleep that never finishes, only phase_over can end the voting phases."""
    s = make_session(phase="WAITING", round_=0)
    closed: list[int] = []

    async def persist(_):
        pass

    async def broadcast(session):
        if session.phase == VOTING:
            session.phase_over.set()  # stands in for the last ballot arriving

    async def end_voting(session):
        closed.append(session.round)

    async def sleep(seconds):
        if s.phase != VOTING:
            return
        await asyncio.Event().wait()  # never wakes on its own

    async def main():
        await asyncio.wait_for(
            run_session(s, exp(), persist=persist, broadcast=broadcast, end_voting=end_voting, sleep=sleep),
            timeout=2,
        )

    asyncio.run(main())
    assert closed == [1, 2] and s.phase == FINAL
