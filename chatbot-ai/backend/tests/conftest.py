import os

# Must be set before any `app.*` module (in particular app.core.config) is
# imported, since settings are loaded once at import time.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:55433/chatbot_test")
os.environ.setdefault("REDIS_URL", "redis://localhost:56379/0")
os.environ.setdefault("JWT_SECRET", "test-secret-key-not-for-production")
os.environ.setdefault("CONFIG_ENCRYPTION_KEY", "RSsN3C3ilKEU80DRFV3J4MvFR4t8FMVVcnFhdgDj-Bw=")
os.environ.setdefault(
    "STORAGE_LOCAL_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "_test_storage")
)

import asyncio
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.core.db import get_db
from app.core.redis_client import get_redis
from app.main import app

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="session")
def event_loop():
    # The cached Redis client (app.core.redis_client.get_redis, an
    # lru_cache singleton — deliberately reused across requests in
    # production) binds its connections to whichever event loop is active
    # on first use. pytest-asyncio's default per-test loop would tear that
    # loop down between tests and break the cached client, so every async
    # test/fixture in this session shares one loop instead.
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
def apply_migrations():
    alembic_cfg = Config(os.path.join(BACKEND_DIR, "alembic.ini"))
    alembic_cfg.set_main_option("script_location", os.path.join(BACKEND_DIR, "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
    command.downgrade(alembic_cfg, "base")
    command.upgrade(alembic_cfg, "head")
    yield


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(settings.DATABASE_URL)
    async with engine.connect() as connection:
        await connection.begin()
        session = AsyncSession(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await connection.rollback()
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    redis_client = get_redis()
    await redis_client.flushdb()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
