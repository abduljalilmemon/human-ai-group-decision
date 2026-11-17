"""WebSocket endpoint and per-session fan-out. All payloads come from protocol.py."""
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from . import protocol
from .lobby import LiveSession

log = logging.getLogger(__name__)
router = APIRouter()


class ConnectionManager:
    """One live socket per player token; a newer connection replaces an older one."""

    def __init__(self):
        self._sockets: dict[str, WebSocket] = {}

    def connect(self, token: str, ws: WebSocket) -> WebSocket | None:
        old = self._sockets.get(token)
        self._sockets[token] = ws
        return old

    def disconnect(self, token: str, ws: WebSocket) -> None:
        if self._sockets.get(token) is ws:
            del self._sockets[token]

    async def send(self, token: str, payload: protocol.Payload) -> None:
        ws = self._sockets.get(token)
        if ws is None:
            return
        try:
            await ws.send_json(payload)
        except Exception:  # socket closed mid-send; its own handler cleans up
            log.debug("send failed for a closed socket")

    async def send_state(self, session: LiveSession) -> None:
        """Send each connected human their own view of the session state."""
        for seat in session.seats:
            if seat.token:
                await self.send(seat.token, protocol.state(session, seat))


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = ""):
    lobby = websocket.app.state.lobby
    manager: ConnectionManager = websocket.app.state.connections
    await websocket.accept()

    found = lobby.find(token)
    if found is None:
        await websocket.send_json(protocol.error("unknown_token"))
        await websocket.close(code=4404)
        return
    session, seat = found

    old = manager.connect(token, websocket)
    if old is not None:
        try:
            await old.close(code=4409)  # replaced by this connection
        except Exception:
            pass
    try:
        await websocket.send_json(protocol.state(session, seat))
        while True:
            await websocket.receive_text()
            # chat and vote handling arrive in slices 4 and 5
            await websocket.send_json(protocol.error("unsupported"))
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(token, websocket)
