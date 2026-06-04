from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import inspect, text
import importlib.util
import os

from ..core.env import load_openmesh_env


load_openmesh_env()


def resolve_database_url() -> str:
    db_mode = os.getenv("OPENMESH_DB_MODE", "auto").lower()
    if db_mode == "sqlite":
        sqlite_path = os.getenv("OPENMESH_SQLITE_PATH", "./openmesh.db")
        return f"sqlite:///{sqlite_path}"
    if db_mode == "postgres":
        return os.getenv(
            "DATABASE_URL",
            "postgresql://openmeshai:password@localhost:5432/openmeshai_db",
        )

    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url

    if os.getenv("ENVIRONMENT", "development").lower() == "development":
        if importlib.util.find_spec("aiosqlite") is None:
            return "postgresql://openmeshai:password@localhost:5432/openmeshai_db"
        sqlite_path = os.getenv("OPENMESH_SQLITE_PATH", "./openmesh.db")
        return f"sqlite:///{sqlite_path}"

    return "postgresql://openmeshai:password@localhost:5432/openmeshai_db"


def to_async_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if database_url.startswith("sqlite:///"):
        return database_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    return database_url


DATABASE_URL = resolve_database_url()
ASYNC_URL = to_async_database_url(DATABASE_URL)

engine_kwargs = {"echo": False}
if ASYNC_URL.startswith("postgresql+"):
    engine_kwargs.update({"pool_size": 10, "max_overflow": 20})

engine = create_async_engine(ASYNC_URL, **engine_kwargs)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db(*, announce: bool = True):
    from .models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_ensure_openmesh_trace_columns)
    if announce:
        print(f"Database tables created ({DATABASE_URL})")


def _ensure_openmesh_trace_columns(sync_connection):
    columns = {
        column["name"]
        for column in inspect(sync_connection).get_columns("openmesh_events")
    }
    required = {
        "span_id": "VARCHAR(100)",
        "parent_span_id": "VARCHAR(100)",
        "parent_event_id": "VARCHAR(100)",
        "root_event_id": "VARCHAR(100)",
        "links_json": "JSON",
    }
    for name, column_type in required.items():
        if name not in columns:
            sync_connection.execute(
                text(f"ALTER TABLE openmesh_events ADD COLUMN {name} {column_type}")
            )
