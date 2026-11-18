import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from . import routes, ws
from .config import ConfigError, load_config
from .db import SessionLocal, create_tables
from .engine import SessionEngine
from .lobby import Lobby

# Fail fast at import: uvicorn exits with this message instead of a traceback.
try:
    settings = load_config()
except ConfigError as e:
    sys.exit(f"\nERROR: {e}\n")

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables()
    connections = ws.ConnectionManager()
    engine = SessionEngine(settings.experiment, SessionLocal, broadcast=connections.send_state)
    app.state.connections = connections
    app.state.lobby = Lobby(settings, SessionLocal, on_start=engine.start)
    yield
    await app.state.lobby.shutdown()
    await engine.shutdown()


app = FastAPI(title="Group Decision Experiment", lifespan=lifespan)
app.include_router(routes.router)
app.include_router(ws.router)

# Registered last so /api and /ws routes take precedence. Absent in local backend-only runs.
if STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
