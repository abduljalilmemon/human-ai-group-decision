"""Chat rules for submit_chat(): the single path every participant's message goes through."""
import asyncio

import pytest

from app.engine import DISCUSSION, FINAL, MAX_CHAT_CHARS, ROUND_RESULT, VOTING, WAITING, submit_chat
from app.lobby import LiveSession, Seat


class Recorder:
    """Fake save and fan-out hooks that remember what they were given."""

    def __init__(self):
        self.saved: list[tuple] = []
        self.sent: list[dict] = []

    async def save(self, session_id, participant_id, round_, text, sent_at) -> int:
        self.saved.append((session_id, participant_id, round_, text, sent_at))
        return len(self.saved)  # new message id

    async def send_all(self, session, payload) -> None:
        self.sent.append(payload)


def make_session(phase: str = DISCUSSION, round_: int = 1) -> LiveSession:
    s = LiveSession(id=9, labels=["Player C", "Player A", "Player B"], human_slots=1, phase=phase, round=round_)
    s.seats = [
        Seat(label="Player C", kind="human", participant_id=31, token="tok-c"),
        Seat(label="Player A", kind="ai", participant_id=32),
    ]
    return s


def send(session: LiveSession, text, rec: Recorder, seat_index: int = 0):
    seat = session.seats[seat_index]
    return asyncio.run(
        submit_chat(session, seat, text, save=rec.save, send_all=rec.send_all, clock=lambda: 1_234_567)
    )


@pytest.mark.parametrize("phase", [WAITING, VOTING, ROUND_RESULT, FINAL])
def test_rejected_outside_discussion_and_nothing_stored(phase):
    rec = Recorder()
    assert send(make_session(phase), "hello", rec) == "chat_closed"
    assert rec.saved == [] and rec.sent == []


@pytest.mark.parametrize("text", ["", "   ", "\n\t "])
def test_empty_rejected(text):
    rec = Recorder()
    assert send(make_session(), text, rec) == "empty_message"
    assert rec.saved == [] and rec.sent == []


def test_too_long_rejected():
    rec = Recorder()
    assert send(make_session(), "x" * (MAX_CHAT_CHARS + 1), rec) == "message_too_long"
    assert rec.saved == [] and rec.sent == []


def test_limit_applies_after_trimming():
    rec = Recorder()
    assert send(make_session(), "  " + "x" * MAX_CHAT_CHARS + "  ", rec) is None
    assert rec.saved[0][3] == "x" * MAX_CHAT_CHARS


@pytest.mark.parametrize("text", [None, 42, ["hi"], {"text": "hi"}])
def test_non_string_rejected(text):
    rec = Recorder()
    assert send(make_session(), text, rec) == "invalid_message"
    assert rec.saved == []


@pytest.mark.parametrize("round_", [1, 2])
def test_saved_with_round_then_broadcast(round_):
    rec = Recorder()
    assert send(make_session(round_=round_), "  I think Player B should lead  ", rec) is None
    assert rec.saved == [(9, 31, round_, "I think Player B should lead", 1_234_567)]
    assert rec.sent == [
        {"type": "message", "id": 1, "from": "Player C", "text": "I think Player B should lead", "sent_at": 1_234_567}
    ]


def test_every_sender_gets_the_same_payload_shape():
    rec = Recorder()
    session = make_session()
    send(session, "hi", rec, seat_index=0)
    send(session, "hi", rec, seat_index=1)
    human, ai = rec.sent
    assert human.keys() == ai.keys()
    assert {k: v for k, v in human.items() if k not in ("id", "from")} == {
        k: v for k, v in ai.items() if k not in ("id", "from")
    }
