"""Test harness.

Runs against PostgreSQL when ``DATABASE_URL`` points at Postgres, and against a
throwaway SQLite file otherwise (which is what CI uses). The previous version
unconditionally issued ``DROP DATABASE`` / ``CREATE DATABASE``, so it could
never work on SQLite even though the workflow set a SQLite URL — the suite
failed before a single test ran.
"""

import os
import uuid

# Make the suite runnable with zero setup: fall back to a throwaway SQLite
# database and a dummy secret when no environment is configured. Must happen
# before app.core.config is imported, since Settings validates on import.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_database.db")
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_ci")
os.environ.setdefault("UPLOAD_DIR", "./uploads")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app

settings = get_settings()
DATABASE_URL = settings.DATABASE_URL
IS_POSTGRES = DATABASE_URL.startswith("postgresql")

# Import every model module so Base.metadata is complete before create_all.
from app.db import models, models_cost, models_phase2, models_phase3  # noqa: E402,F401


def _postgres_urls() -> tuple[str, str]:
    base = "/".join(DATABASE_URL.split("/")[:-1])
    return f"{base}/postgres", f"{base}/ethioqs_test_shared"


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_db():
    if IS_POSTGRES:
        from sqlalchemy import text

        admin_url, test_url = _postgres_urls()
        admin_engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
        async with admin_engine.connect() as conn:
            await conn.execute(
                text(
                    "SELECT pg_terminate_backend(pg_stat_activity.pid) "
                    "FROM pg_stat_activity "
                    "WHERE pg_stat_activity.datname = 'ethioqs_test_shared' "
                    "AND pid <> pg_backend_pid();"
                )
            )
            await conn.execute(text("DROP DATABASE IF EXISTS ethioqs_test_shared"))
            await conn.execute(text("CREATE DATABASE ethioqs_test_shared"))
        await admin_engine.dispose()
        engine = create_async_engine(test_url)
    else:
        # SQLite: a fresh file per session, in the system temp dir.
        db_path = os.path.join(
            os.environ.get("TMPDIR", "/tmp"), f"dm_test_{uuid.uuid4().hex}.db"
        )
        engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app.state.test_engine = engine
    yield

    await engine.dispose()
    if not IS_POSTGRES and os.path.exists(db_path):
        os.remove(db_path)


@pytest_asyncio.fixture
async def db_session():
    session_factory = async_sessionmaker(app.state.test_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session):
    async def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
