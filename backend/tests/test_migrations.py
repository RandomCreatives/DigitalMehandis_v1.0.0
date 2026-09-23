"""The Alembic baseline must match the models exactly."""
import asyncio
import pathlib

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import command
from alembic.config import Config
from app.db.base import Base

from tests.conftest import TEST_DB_URL

BACKEND = pathlib.Path(__file__).resolve().parents[1]


def test_single_head():
    from alembic.script import ScriptDirectory
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "app/db/migrations"))
    assert len(ScriptDirectory.from_config(cfg).get_heads()) == 1


async def test_migrations_match_models(monkeypatch):
    url = TEST_DB_URL.render_as_string(hide_password=False)
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")
    await engine.dispose()

    monkeypatch.setenv("DATABASE_URL", url)
    from app.core.config import get_settings
    get_settings.cache_clear()
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "app/db/migrations"))
    try:
        await asyncio.to_thread(command.upgrade, cfg, "head")
    finally:
        get_settings.cache_clear()

    engine = create_async_engine(url)
    async with engine.connect() as conn:
        diff = await conn.run_sync(
            lambda c: compare_metadata(MigrationContext.configure(c), Base.metadata)
        )
    # restore schema for other tests
    async with engine.begin() as conn:
        await conn.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    assert diff == [], diff
