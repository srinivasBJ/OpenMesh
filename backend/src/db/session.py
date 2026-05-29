from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
import importlib.util
import os


def resolve_database_url() -> str:
    db_mode = os.getenv("OPENMESH_DB_MODE", "auto").lower()
    if db_mode == "sqlite":
        sqlite_path = os.getenv("OPENMESH_SQLITE_PATH", "./openmesh.db")
        return f"sqlite:///{sqlite_path}"
    if db_mode == "postgres":
        return os.getenv("DATABASE_URL", "postgresql://openmeshai:password@localhost:5432/openmeshai_db")

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


async def init_db():
    from .models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print(f"✅ Database tables created ({DATABASE_URL})")
