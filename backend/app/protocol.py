"""Builds every outbound payload (REST responses and WebSocket messages).

Blind condition: each builder copies an explicit allow-list of public fields. Never pass a DB model
or an internal object through, and never add a participant's kind or another player's token.
"""
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .lobby import LiveSession, Seat

Payload = dict[str, Any]


def now_ms() -> int:
    """Wire time format: Unix epoch in milliseconds."""
    return int(time.time() * 1000)


def join_response(token: str) -> Payload:
    """The caller's own token only."""
    return {"token": token}


def state(session: "LiveSession", seat: "Seat", server_now: int | None = None) -> Payload:
    server_now = now_ms() if server_now is None else server_now
    ends_at = session.phase_ends_at
    started = session.phase != "WAITING"
    return {
        "type": "state",
        "phase": session.phase,
        "round": session.round,
        "phase_ends_at": ends_at,
        "server_now": server_now,
        "remaining_ms": None if ends_at is None else max(0, ends_at - server_now),
        # Labels are revealed only once the session starts, so the waiting room shows nothing
        # about who or how many have joined.
        "you": seat.label if started else None,
        "players": sorted(s.label for s in session.seats) if started else [],
        "has_voted": session.has_voted(seat.label),  # own ballot only, never anyone else's
        # Random per session and identical for every seat; seeds the client's avatar deal.
        "avatar_seed": session.avatar_seed if started else None,
    }


def round_result(round_: int, tallies: dict[str, int]) -> Payload:
    """Anonymous tally: counts per label, never who voted for whom."""
    return {"type": "round_result", "round": round_, "tallies": dict(tallies)}


def final_result(decision_maker: str, tallies_by_round: dict[int, dict[str, int]], tie_break: str) -> Payload:
    return {
        "type": "final_result",
        "decision_maker": decision_maker,
        "tallies_by_round": {str(r): dict(t) for r, t in sorted(tallies_by_round.items())},
        "tie_break": tie_break,
    }


def message(message_id: int, from_label: str, text: str, sent_at: int) -> Payload:
    """A chat line. Identical shape for every sender: only the public label identifies them."""
    return {"type": "message", "id": message_id, "from": from_label, "text": text, "sent_at": sent_at}


def error(reason: str) -> Payload:
    return {"type": "error", "reason": reason}


def replay(session: "LiveSession", seat: "Seat", server_now: int | None = None) -> list[Payload]:
    """Everything a (re)connecting client needs, in order: its own state, the chat so far, then any
    round tally and final result already shown. Built only from the builders above."""
    payloads = [state(session, seat, server_now)]
    payloads += [message(m.id, m.label, m.text, m.sent_at) for m in session.chat]
    payloads += [round_result(r, t) for r, t in sorted(session.shown_tallies.items())]
    if session.final is not None:
        payloads.append(final_result(*session.final))
    return payloads
