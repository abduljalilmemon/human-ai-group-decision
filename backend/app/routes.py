"""REST endpoints. Deliberately no export or admin route: it could expose participant type."""
from fastapi import APIRouter, Request

from . import protocol

router = APIRouter(prefix="/api")


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.post("/join")
async def join(request: Request):
    token = await request.app.state.lobby.join()
    return protocol.join_response(token)
