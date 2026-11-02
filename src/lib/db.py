from pathlib import Path
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel


class DatabaseAdapter:
    """Async SQLite persistence adapter for SQLModel entities."""

    DATA_DIR = Path.cwd().resolve() / "data"
    DEFAULT_DB_URL = f"sqlite+aiosqlite:///{DATA_DIR / 'auricue.db'}"

    def __init__(self, url: str = DEFAULT_DB_URL) -> None:
        self.engine = create_async_engine(url)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def init(self) -> None:
        """Create all SQLModel tables if they do not exist."""

        async with self.engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

    async def save(self, *objs: SQLModel) -> None:
        """Insert or update one or more SQLModel rows."""

        async with self.sessions.begin() as s:
            s.add_all(objs)

    async def close(self) -> None:
        await self.engine.dispose()


__all__ = ["DatabaseAdapter"]
