"""Reconnect and disconnects: replay on reconnect, waiting-room seat release, abstention when absent."""
import asyncio

import pytest

from app import protocol
from app.config import AI, Config, Experiment, Participant as ParticipantCfg
from app.engine import (
    DISCUSSION, FINAL, ROUND_RESULT, VOTING, WAITING, close_voting, run_session, submit_chat, submit_vote,
)
from app.lobby import ChatRecord, LiveSession, Lobby, Seat
from app.models import Event, Participant
from app.ws import CLOSE_REPLACED, ConnectionManager

A, B, C = "Player A", "Player B", "Player C"
TALLY = {A: 2, B: 1, C: 0}


def exp() -> Experiment:
    return Experiment(discussion_seconds=10, voting_seconds=5, results_pause_seconds=3, min_wait_seconds=(0.01, 0.01))


def make_session(phase: str, round_: int) -> LiveSession:
    s = LiveSession(id=7, labels=[C, A, B], human_slots=2, phase=phase, round=round_)
    s.phase_ends_at = None if phase in (WAITING, FINAL) else 2_000_000
    s.seats = [
        Seat(label=C, kind="human", participant_id=1, token="tok-c"),
        Seat(label=A, kind="human", participant_id=2, token="tok-a"),
        Seat(label=B, kind="ai", participant_id=3),
    ]
    return s


def types(payloads: list[dict]) -> list[str]:
    return [p["type"] for p in payloads]


# --- Replay: what a reconnecting client receives, in every phase --------------------------------

def test_replay_waiting_is_state_only_and_hides_seats():
    s = make_session(WAITING, 0)
    s.seats = s.seats[:1]
    (state,) = protocol.replay(s, s.seats[0], server_now=1_000_000)
    assert state["phase"] == WAITING and state["players"] == [] and state["you"] is None


def test_replay_discussion_has_state_then_chat_in_order():
    s = make_session(DISCUSSION, 1)
    s.chat = [ChatRecord(1, A, "hi", 10), ChatRecord(2, B, "hey", 20)]
    out = protocol.replay(s, s.seats[0], server_now=1_990_000)
    assert types(out) == ["state", "message", "message"]
    assert out[0]["remaining_ms"] == 10_000 and out[0]["you"] == C
    assert [(m["id"], m["from"], m["text"]) for m in out[1:]] == [(1, A, "hi"), (2, B, "hey")]


def test_replay_voting_keeps_own_has_voted_only():
    s = make_session(VOTING, 1)
    s.ballots = {1: {C: A}}
    voted, other = protocol.replay(s, s.seats[0])[0], protocol.replay(s, s.seats[1])[0]
    assert voted["has_voted"] is True and other["has_voted"] is False


def test_replay_round_result_includes_the_tally_shown():
    s = make_session(ROUND_RESULT, 1)
    s.chat = [ChatRecord(1, A, "hi", 10)]
    s.shown_tallies = {1: TALLY}
    out = protocol.replay(s, s.seats[0])
    assert types(out) == ["state", "message", "round_result"]
    assert out[-1] == protocol.round_result(1, TALLY)


def test_replay_round_two_keeps_round_one_chat_and_tally():
    s = make_session(DISCUSSION, 2)
    s.chat = [ChatRecord(1, A, "r1", 10), ChatRecord(2, C, "r2", 20)]
    s.shown_tallies = {1: TALLY}
    out = protocol.replay(s, s.seats[1])
    assert types(out) == ["state", "message", "message", "round_result"]
    assert out[0]["round"] == 2


def test_replay_final_includes_final_result():
    s = make_session(FINAL, 2)
    s.shown_tallies = {1: TALLY}
    s.final = (A, {1: TALLY, 2: TALLY}, "none")
    out = protocol.replay(s, s.seats[0])
    assert types(out) == ["state", "round_result", "final_result"]
    assert out[0]["remaining_ms"] is None
    assert out[-1] == protocol.final_result(A, {1: TALLY, 2: TALLY}, "none")


def test_engine_records_what_replay_needs():
    """submit_chat and close_voting store the chat, tallies and result they broadcast."""
    s = make_session(DISCUSSION, 1)
    sent: list[dict] = []

    async def send_all(_s, payload):
        sent.append(payload)

    async def save_msg(*_):
        return len(s.chat) + 1

    async def save(*_):
        pass

    async def send_state(*_):
        pass

    async def main():
        await submit_chat(s, s.seats[0], " hello ", save=save_msg, send_all=send_all, clock=lambda: 5)
        s.phase = VOTING
        await submit_vote(s, s.seats[0], A, save=save, send_state=send_state)
        await close_voting(s, exp(), save=save, save_decision=save, send_all=send_all)
        s.phase, s.round = VOTING, 2
        await close_voting(s, exp(), save=save, save_decision=save, send_all=send_all)

    asyncio.run(main())
    s.phase = FINAL
    replayed = protocol.replay(s, s.seats[1])[1:]
    assert replayed == sent  # the replay is exactly what was broadcast live
    assert types(replayed) == ["message", "round_result", "final_result"]


# --- ConnectionManager: replay delivery and the replaced tab -----------------------------------

class FakeSocket:
    def __init__(self):
        self.sent: list[dict] = []
        self.closed: int | None = None

    async def send_json(self, payload):
        if self.closed is not None:
            raise RuntimeError("closed")
        self.sent.append(payload)
        await asyncio.sleep(0)  # yield, so a concurrent broadcast could interleave without the lock

    async def close(self, code=1000):
        self.closed = code


def test_attach_sends_replay_before_any_concurrent_broadcast():
    s = make_session(DISCUSSION, 1)
    s.chat = [ChatRecord(1, A, "a", 1), ChatRecord(2, A, "b", 2)]
    manager, ws = ConnectionManager(), FakeSocket()

    async def main():
        attach = asyncio.create_task(manager.attach("tok-c", ws, protocol.replay(s, s.seats[0])))
        await asyncio.sleep(0)  # attach has started sending
        await manager.send_all(s, protocol.message(3, B, "live", 3))
        await attach

    asyncio.run(main())
    assert [m.get("id") for m in ws.sent] == [None, 1, 2, 3]  # state, replayed chat, then the live line


def test_newer_connection_replaces_older_with_a_clear_message():
    s = make_session(DISCUSSION, 1)
    manager, old, new = ConnectionManager(), FakeSocket(), FakeSocket()

    async def main():
        await manager.attach("tok-c", old, protocol.replay(s, s.seats[0]))
        await manager.attach("tok-c", new, protocol.replay(s, s.seats[0]))
        manager.disconnect("tok-c", old)  # the old handler's cleanup must not drop the new socket
        await manager.send_all(s, protocol.message(1, A, "hi", 1))
        await manager.send("tok-c", protocol.error("chat_closed"), only_to=old)  # stale sender: dropped

    asyncio.run(main())
    assert old.sent[-1] == protocol.error("replaced") and old.closed == CLOSE_REPLACED
    assert types(new.sent) == ["state", "message"] and new.closed is None


# --- Waiting room: seat release after a grace period --------------------------------------------

class FakeDB:
    """Just enough of an AsyncSession for the lobby: rows get ids on add, and are kept per table."""

    def __init__(self):
        self.rows: list = []
        self.deleted: list = []
        self._next_id = 0

    def __call__(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def add(self, row):
        self._next_id += 1
        row.id = self._next_id
        self.rows.append(row)

    def add_all(self, rows):
        for row in rows:
            self.add(row)

    async def flush(self):
        pass

    async def commit(self):
        pass

    async def get(self, model, id_):
        return next((r for r in self.rows if isinstance(r, model) and r.id == id_), None)

    async def delete(self, row):
        self.rows.remove(row)
        self.deleted.append(row)

    def of(self, model):
        return [r for r in self.rows if isinstance(r, model)]


def config(humans: int) -> Config:
    return Config(
        experiment=exp(),
        labels=[A, B, C],
        participants=[ParticipantCfg(type="human" if i < humans else "ai") for i in range(3)],
        ai=AI(provider="scripted", model="x"),
    )


GRACE = 0.05


def make_lobby(humans: int = 3):
    db, started = FakeDB(), []

    async def on_start(session):
        started.append(session)

    return Lobby(config(humans), db, on_start=on_start, grace_seconds=GRACE), db, started


def test_closed_tab_releases_its_waiting_room_seat_after_grace():
    lobby, db, _ = make_lobby()

    async def main():
        token = await lobby.join()
        lobby.connected(token)
        lobby.disconnected(token)
        await asyncio.sleep(GRACE / 2)
        assert lobby.find(token) is not None  # still held during the grace period
        await asyncio.sleep(GRACE)
        return token

    token = asyncio.run(main())
    assert lobby.find(token) is None  # the WebSocket endpoint now answers unknown_token
    assert db.of(Participant) == [] and len(db.deleted) == 1
    assert [e.type for e in db.of(Event)] == ["seat_released"]


def test_refresh_within_grace_keeps_the_seat():
    lobby, db, _ = make_lobby()

    async def main():
        token = await lobby.join()
        lobby.connected(token)
        lobby.disconnected(token)  # page unloads...
        await asyncio.sleep(GRACE / 2)
        lobby.connected(token)  # ...and reconnects with the same token
        await asyncio.sleep(GRACE * 2)
        return token

    token = asyncio.run(main())
    session, seat = lobby.find(token)
    assert session.seats == [seat] and len(db.of(Participant)) == 1 and db.deleted == []


def test_released_label_goes_to_the_next_joiner_without_duplicates():
    lobby, db, started = make_lobby()

    async def main():
        first, second = await lobby.join(), await lobby.join()
        freed = lobby.find(first)[1].label
        lobby.connected(first)
        lobby.disconnected(first)
        await asyncio.sleep(GRACE * 2)
        third, fourth = await lobby.join(), await lobby.join()
        await asyncio.sleep(0.05)  # randomized start delay
        return freed, [lobby.find(t)[1].label for t in (second, third, fourth)]

    freed, labels = asyncio.run(main())
    assert sorted(labels) == [A, B, C] and freed in labels
    assert len(started) == 1 and len(started[0].seats) == 3  # the session still filled and started


def test_no_release_once_the_session_is_full():
    """After every human seat is filled the session is starting; a closed tab just stays absent."""
    lobby, db, started = make_lobby(humans=1)

    async def main():
        token = await lobby.join()
        lobby.connected(token)
        lobby.disconnected(token)
        await asyncio.sleep(GRACE * 2)
        return token

    token = asyncio.run(main())
    assert lobby.find(token) is not None and db.deleted == []
    assert len(started) == 1 and len(started[0].seats) == 3  # 1 human + 2 AI


def test_a_replaced_tab_closing_does_not_start_a_release():
    lobby, db, _ = make_lobby()

    async def main():
        token = await lobby.join()
        lobby.connected(token)  # first tab
        lobby.connected(token)  # duplicated tab takes over
        lobby.disconnected(token)  # first tab is closed by the server
        await asyncio.sleep(GRACE * 2)
        return token

    assert lobby.find(asyncio.run(main())) is not None and db.deleted == []


# --- Avatar seed: one random value per session, the same for every seat and every reconnect ------

def test_avatar_seed_is_present_identical_across_seats_and_stable_on_reconnect():
    s = make_session(DISCUSSION, 1)
    seeds = {protocol.state(s, seat)["avatar_seed"] for seat in s.seats}  # includes the AI seat's view
    assert seeds == {s.avatar_seed} and s.avatar_seed
    s.chat = [ChatRecord(1, A, "hi", 10)]
    s.phase, s.round = VOTING, 2  # later phase, then a reconnect
    assert protocol.replay(s, s.seats[0])[0]["avatar_seed"] == s.avatar_seed


def test_avatar_seed_hidden_in_the_waiting_room():
    s = make_session(WAITING, 0)
    assert protocol.state(s, s.seats[0])["avatar_seed"] is None


def test_lobby_seed_is_random_per_session_and_logged_at_start():
    lobby, db, started = make_lobby(humans=1)

    async def main():
        await lobby.join()
        await lobby.join()  # lands in a second session
        await asyncio.sleep(0.05)

    asyncio.run(main())
    first, second = started
    assert first.avatar_seed != second.avatar_seed
    assert first.avatar_seed not in (str(first.id), str(second.id))
    logged = [e.payload["seed"] for e in db.of(Event) if e.type == "avatar_dealt"]
    assert logged == [first.avatar_seed, second.avatar_seed]


# --- A disconnected human does not stop the session ----------------------------------------------

def test_disconnected_human_abstains_and_others_finish():
    s = make_session(WAITING, 0)
    manager, present = ConnectionManager(), FakeSocket()  # tok-a never reconnects
    saved_votes: list[tuple] = []
    decisions: list[tuple] = []

    async def save(_sid, round_, votes):
        saved_votes.extend((round_, voter, target) for voter, target in votes)

    async def save_decision(_sid, winner_id, tie_break, _t):
        decisions.append((winner_id, tie_break))

    async def end_voting(session):
        if session.phase == VOTING:  # the present human and the AI vote; Player A is gone
            for seat in (session.seats[0], session.seats[2]):
                await submit_vote(session, seat, C, save=save, send_state=manager.send_state_to)
        await close_voting(session, exp(), save=save, save_decision=save_decision, send_all=manager.send_all)

    async def persist(_):
        pass

    async def no_sleep(_):
        pass

    async def main():
        await manager.attach("tok-c", present, protocol.replay(s, s.seats[0]))
        await asyncio.wait_for(
            run_session(s, exp(), persist=persist, broadcast=manager.send_state, end_voting=end_voting, sleep=no_sleep),
            timeout=2,
        )

    asyncio.run(main())
    assert s.phase == FINAL
    assert [(r, t) for r, v, t in saved_votes if v == 2] == [(1, None), (2, None)]  # abstained both rounds
    assert decisions == [(1, "none")]  # Player C won with the votes that were cast
    final = [m for m in present.sent if m["type"] == "final_result"]
    assert len(final) == 1 and final[0]["decision_maker"] == C  # the present human still got the result
    assert present.sent[-1]["phase"] == FINAL
