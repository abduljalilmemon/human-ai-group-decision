"""Every protocol builder's output must be free of participant type and other players' tokens."""
import json

import pytest

from app import protocol
from app.lobby import LiveSession, Seat

TOKENS = {"Player A": "token-aaa-secret", "Player B": "token-bbb-secret"}


def make_session(phase: str) -> LiveSession:
    s = LiveSession(id=7, labels=["Player B", "Player C", "Player A"], human_slots=2, phase=phase)
    s.seats = [
        Seat(label="Player A", kind="human", participant_id=1, token=TOKENS["Player A"]),
        Seat(label="Player B", kind="human", participant_id=2, token=TOKENS["Player B"]),
        Seat(label="Player C", kind="ai", participant_id=3),
    ]
    if phase != "WAITING":
        s.round, s.phase_ends_at = 1, 2_000_000
    return s


def keys_and_values(obj):
    """All dict keys and scalar values, recursively."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from keys_and_values(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from keys_and_values(v)
    else:
        yield obj


def assert_blind(payload, own_token: str | None = None):
    items = {str(x).lower() for x in keys_and_values(payload)}
    for banned in ("kind", "human", "ai", "participant_type", "participant_id", "token_of"):
        assert banned not in items, banned
    text = json.dumps(payload)
    for token in TOKENS.values():
        if token != own_token:
            assert token not in text


def all_payloads():
    yield protocol.join_response(TOKENS["Player A"]), TOKENS["Player A"]
    yield protocol.error("unsupported"), None
    yield protocol.message(1, "Player C", "hi there", 1_990_000), None
    tallies = {"Player A": 1, "Player B": 0, "Player C": 2}
    yield protocol.round_result(1, tallies), None
    yield protocol.final_result("Player C", {1: tallies, 2: tallies}, "none"), None
    for phase in ("WAITING", "DISCUSSION", "VOTING", "ROUND_RESULT", "FINAL"):
        session = make_session(phase)
        for seat in session.seats:
            yield protocol.state(session, seat, server_now=1_990_000), None


@pytest.mark.parametrize("payload, own_token", list(all_payloads()))
def test_no_kind_or_foreign_token(payload, own_token):
    assert_blind(payload, own_token)


def test_state_timing_fields():
    payload = protocol.state(make_session("DISCUSSION"), make_session("DISCUSSION").seats[0], server_now=1_990_000)
    assert payload["phase_ends_at"] == 2_000_000
    assert payload["server_now"] == 1_990_000
    assert payload["remaining_ms"] == 10_000
    late = protocol.state(make_session("VOTING"), make_session("VOTING").seats[0], server_now=2_500_000)
    assert late["remaining_ms"] == 0  # never negative
    final = make_session("FINAL")
    final.phase_ends_at = None
    assert protocol.state(final, final.seats[0])["remaining_ms"] is None


def test_state_has_voted_is_own_ballot_only():
    s = make_session("VOTING")
    s.ballots[1] = {"Player A": "Player C"}
    by_label = {seat.label: protocol.state(s, seat)["has_voted"] for seat in s.seats}
    assert by_label == {"Player A": True, "Player B": False, "Player C": False}


def test_results_never_name_voters():
    payload = protocol.round_result(1, {"Player A": 2, "Player B": 1, "Player C": 0})
    assert set(payload) == {"type", "round", "tallies"}
    final = protocol.final_result("Player A", {1: {"Player A": 2}}, "none")
    assert set(final) == {"type", "decision_maker", "tallies_by_round", "tie_break"}


def test_waiting_state_reveals_no_seats():
    payload = protocol.state(make_session("WAITING"), make_session("WAITING").seats[0])
    assert payload["players"] == [] and payload["you"] is None
