import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .config import ConfigError, load_config
from .db import create_tables

# Fail fast at import: uvicorn exits with this message instead of a traceback.
try:
    settings = load_config()
except ConfigError as e:
    sys.exit(f"\nERROR: {e}\n")

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables()
    yield


app = FastAPI(title="Group Decision Experiment", lifespan=lifespan)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


# Registered last so /api and /ws routes take precedence. Absent in local backend-only runs.
if STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
