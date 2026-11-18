"""Blind condition: nothing a client receives may reveal whether a participant is human or AI."""
import asyncio
import random

import pytest

from app import protocol
from app.agents.base import (
    MAX_AGENT_CHARS, MAX_REPLY_SECONDS, MIN_REPLY_SECONDS, clean_reply, has_tell, reply_delay, vote_delay,
)
from app.engine import DISCUSSION, submit_chat
from app.lobby import ChatRecord, LiveSession, Seat

BANNED_KEYS = {
    "kind", "type_of", "participant_type", "is_ai", "is_human", "human", "ai", "bot", "agent", "model",
    "participant_id", "token_of",
}
BANNED_VALUES = {"human", "ai", "bot", "agent", "scripted", "llm"}


def make_session(phase: str = DISCUSSION) -> LiveSession:
    s = LiveSession(id=3, labels=["Player C", "Player A", "Player B"], human_slots=1, phase=phase, round=1)
    s.phase_ends_at = 2_000_000
    s.seats = [
        Seat(label="Player C", kind="human", participant_id=11, token="tok-human"),
        Seat(label="Player A", kind="ai", participant_id=12),
        Seat(label="Player B", kind="ai", participant_id=13),
    ]
    return s


def walk(obj, keys: set, values: set):
    if isinstance(obj, dict):
        for k, v in obj.items():
            keys.add(str(k).lower())
            walk(v, keys, values)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            walk(v, keys, values)
    else:
        values.add(str(obj).lower())


def every_payload():
    tallies = {"Player A": 1, "Player B": 1, "Player C": 1}
    yield "join_response", protocol.join_response("tok-human")
    yield "message", protocol.message(1, "Player A", "hey all", 1_999_000)
    yield "round_result", protocol.round_result(1, tallies)
    yield "final_result", protocol.final_result("Player A", {1: tallies, 2: tallies}, "random")
    yield "error", protocol.error("chat_closed")
    for phase in ("WAITING", "DISCUSSION", "VOTING", "ROUND_RESULT", "FINAL"):
        session = make_session(phase)
        for seat in session.seats:  # including the view an AI seat would get
            yield f"state/{phase}/{seat.kind}", protocol.state(session, seat, server_now=1_990_000)
    # The reconnect replay, with chat from both kinds of seat, a shown tally and a final result.
    session = make_session("FINAL")
    session.chat = [ChatRecord(1, "Player C", "hi", 1), ChatRecord(2, "Player A", "hey", 2)]
    session.shown_tallies = {1: tallies}
    session.final = ("Player A", {1: tallies, 2: tallies}, "round1")
    for i, payload in enumerate(protocol.replay(session, session.seats[0], server_now=1_990_000)):
        yield f"replay/{i}/{payload['type']}", payload


@pytest.mark.parametrize("name, payload", list(every_payload()))
def test_no_payload_reveals_participant_type(name, payload):
    keys, values = set(), set()
    walk(payload, keys, values)
    assert not keys & BANNED_KEYS, name
    assert not values & BANNED_VALUES, name


def test_ai_and_human_messages_have_identical_shape():
    sent: list[dict] = []

    async def save(*_args) -> int:
        return len(sent) + 1

    async def send_all(_session, payload) -> None:
        sent.append(payload)

    async def run():
        session = make_session()
        human, ai = session.seats[0], session.seats[1]
        for seat in (human, ai):  # the same submit_chat path for both
            assert await submit_chat(session, seat, "i think B", save=save, send_all=send_all, clock=lambda: 5) is None

    asyncio.run(run())
    human_msg, ai_msg = sent
    assert human_msg.keys() == ai_msg.keys()
    assert {k: type(v) for k, v in human_msg.items()} == {k: type(v) for k, v in ai_msg.items()}
    assert {k: v for k, v in human_msg.items() if k not in ("id", "from")} == \
        {k: v for k, v in ai_msg.items() if k not in ("id", "from")}


@pytest.mark.parametrize("text", [
    "As an AI, I can't vote",
    "i'm just a language model lol",
    "I am an LLM so no preference",
    "beep boop i'm a bot",
    "As an assistant I would say B",
    "Claude here, B seems good",
    "trained by Anthropic",
    "artificial intelligence would pick A",
])
def test_filter_blocks_ai_tells(text):
    assert has_tell(text)
    assert clean_reply(text, "Player A") is None


@pytest.mark.parametrize("text", [
    "i'd go with B tbh",
    "hmm fair point, wait what would you decide?",
    "Player C said it well",
    "maybe aim for someone calm",  # 'aim' contains 'ai' but is not the word
])
def test_filter_allows_normal_chat(text):
    assert not has_tell(text)
    assert clean_reply(text, "Player A") == text


def test_clean_reply_normalises():
    assert clean_reply('Player A:  "ok  fine"', "Player A") == "ok fine"
    assert clean_reply("   ", "Player A") is None
    assert clean_reply(None, "Player A") is None
    assert clean_reply("x" * (MAX_AGENT_CHARS + 1), "Player A") is None


def test_reply_delay_grows_with_length():
    short = reply_delay("ok", random.Random(1))
    long = reply_delay("honestly i think whoever explains their reasoning", random.Random(1))
    assert long > short  # same seed, so only the length differs


def test_reply_delay_is_bounded_and_jittered():
    text = "i'd go with player b, they seem calm"
    delays = [reply_delay(text, random.Random(seed)) for seed in range(200)]
    assert all(MIN_REPLY_SECONDS <= d <= MAX_REPLY_SECONDS for d in delays)
    assert len({round(d, 3) for d in delays}) > 50  # random jitter, not a fixed delay
    assert reply_delay("x" * 1000, random.Random(0)) == MAX_REPLY_SECONDS
    assert reply_delay("", random.Random(0)) >= MIN_REPLY_SECONDS


@pytest.mark.parametrize("remaining", [3.0, 5.0, 20.0])
def test_vote_delay_lands_before_the_deadline(remaining):
    delays = [vote_delay(remaining, random.Random(seed)) for seed in range(200)]
    assert all(0.25 * remaining <= d <= 0.65 * remaining < remaining for d in delays)
    assert len({round(d, 3) for d in delays}) > 50
