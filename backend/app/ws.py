"""WebSocket endpoint and per-session fan-out. All payloads come from protocol.py."""
import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from . import protocol
from .lobby import LiveSession, Seat

log = logging.getLogger(__name__)
router = APIRouter()

CLOSE_UNKNOWN_TOKEN = 4404
CLOSE_REPLACED = 4409


class ConnectionManager:
    """One live socket per player token; a newer connection replaces an older one.

    Each socket has a send lock so frames never interleave: a replay is sent as one block, and a
    broadcast that arrives meanwhile waits until the replay is done.
    """

    def __init__(self):
        self._sockets: dict[str, tuple[WebSocket, asyncio.Lock]] = {}

    async def attach(self, token: str, ws: WebSocket, replay: list[protocol.Payload]) -> None:
        """Register ws for token, send it the replay, and tell any older socket it was replaced."""
        old = self._sockets.get(token)
        lock = asyncio.Lock()
        self._sockets[token] = (ws, lock)
        async with lock:  # taken before any await, so no broadcast can slip in ahead of the replay
            for payload in replay:
                await ws.send_json(payload)
        if old is not None:
            async with old[1]:
                await _close_quietly(old[0], CLOSE_REPLACED, protocol.error("replaced"))

    def disconnect(self, token: str, ws: WebSocket) -> None:
        current = self._sockets.get(token)
        if current is not None and current[0] is ws:
            del self._sockets[token]

    async def send(self, token: str, payload: protocol.Payload, only_to: WebSocket | None = None) -> None:
        """Send to the player's current socket. With only_to, skip it if that socket was replaced."""
        entry = self._sockets.get(token)
        if entry is None:  # disconnected: the session carries on without this player
            return
        ws, lock = entry
        if only_to is not None and ws is not only_to:
            return
        try:
            async with lock:
                await ws.send_json(payload)
        except Exception:  # socket closed mid-send; its own handler cleans up
            log.debug("send failed for a closed socket")

    async def send_all(self, session: LiveSession, payload: protocol.Payload) -> None:
        """Send the same payload to every connected human in the session."""
        for seat in session.seats:
            if seat.token:
                await self.send(seat.token, payload)

    async def send_state(self, session: LiveSession) -> None:
        """Send each connected human their own view of the session state."""
        for seat in session.seats:
            if seat.token:
                await self.send(seat.token, protocol.state(session, seat))

    async def send_state_to(self, session: LiveSession, seat: Seat) -> None:
        """Send one player their own state (e.g. to confirm their vote). No-op for AI seats."""
        if seat.token:
            await self.send(seat.token, protocol.state(session, seat))


async def _close_quietly(ws: WebSocket, code: int, payload: protocol.Payload) -> None:
    try:
        await ws.send_json(payload)
        await ws.close(code=code)
    except Exception:  # already gone
        pass


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = ""):
    lobby = websocket.app.state.lobby
    engine = websocket.app.state.engine
    manager: ConnectionManager = websocket.app.state.connections
    await websocket.accept()

    found = lobby.find(token)
    if found is None:  # never issued, released from the waiting room, or lost in a server restart
        await _close_quietly(websocket, CLOSE_UNKNOWN_TOKEN, protocol.error("unknown_token"))
        return
    session, seat = found
    lobby.connected(token)  # no await since find(), so a pending seat release sees this connection
    try:
        await manager.attach(token, websocket, protocol.replay(session, seat))
        while True:
            try:
                msg = json.loads(await websocket.receive_text())
            except ValueError:
                msg = None
            if not isinstance(msg, dict):
                reason = "invalid_message"
            elif msg.get("type") == "chat":
                reason = await engine.submit_chat(session, seat, msg.get("text"))
            elif msg.get("type") == "vote":
                reason = await engine.submit_vote(session, seat, msg.get("target"))
            else:
                reason = "unsupported"
            if reason:
                await manager.send(token, protocol.error(reason), only_to=websocket)  # sender only
    except WebSocketDisconnect:
        pass
    except Exception:  # e.g. the replay failed because the client left at once
        log.debug("websocket closed with an error", exc_info=True)
    finally:
        manager.disconnect(token, websocket)
        lobby.disconnected(token)
