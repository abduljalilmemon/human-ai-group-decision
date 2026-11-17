import os

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from .models import Base

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/experiment"
)

engine = create_async_engine(DATABASE_URL)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def create_tables() -> None:
    # No migration tool by design: tables are created at startup (see README trade-offs).
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
