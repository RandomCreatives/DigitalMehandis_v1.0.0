"""
Test fixtures.

Tests run against the database given by ``TEST_DATABASE_URL`` (falls back to
``DATABASE_URL``):

* ``sqlite+aiosqlite://...``  → a throw-away SQLite file (fast, no server needed)
* ``postgresql+asyncpg://...`` → a dedicated ``<db>_test`` database is created
  and dropped around the test session.

The schema is created with ``Base.metadata.create_all`` from the model
registry; ``tests/test_migrations.py`` separately checks that the Alembic
baseline matches the models.
"""
import os
import tempfile

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db import registry  # noqa: F401 — register every module's models
from app.db.base import Base
from app.db.session import get_db
from app.main import app

_base_url = make_url(os.environ.get("TEST_DATABASE_URL") or get_settings().DATABASE_URL)

if _base_url.get_backend_name() == "sqlite":
    _tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    TEST_DB_URL = _base_url.set(database=_tmp.name)
    ADMIN_URL = None
else:
    TEST_DB_URL = _base_url.set(database=f"{_base_url.database}_test")
    ADMIN_URL = _base_url.set(database="postgres")


async def _recreate_pg_database(drop_only: bool = False) -> None:
    admin = create_async_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    async with admin.connect() as conn:
        name = TEST_DB_URL.database
        await conn.execute(text(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = :n AND pid <> pg_backend_pid()"
        ), {"n": name})
        await conn.execute(text(f'DROP DATABASE IF EXISTS "{name}"'))
        if not drop_only:
            await conn.execute(text(f'CREATE DATABASE "{name}"'))
    await admin.dispose()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_db():
    if ADMIN_URL is not None:
        await _recreate_pg_database()
    engine = create_async_engine(TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    yield
    if ADMIN_URL is not None:
        await _recreate_pg_database(drop_only=True)
    else:
        os.unlink(TEST_DB_URL.database)


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(TEST_DB_URL)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    # Isolation: wipe all rows after each test.
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session):
    async def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
