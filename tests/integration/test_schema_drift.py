"""O schema que as migrations constroem tem que ser o que os modelos declaram."""

import asyncio

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

import app.models  # noqa: F401  (registra as tabelas no metadata)
from app.core.config import settings
from app.core.database import Base

pytestmark = pytest.mark.integration


def test_migrations_and_models_have_no_drift():
    async def compare():
        engine = create_async_engine(settings.DATABASE_URI, poolclass=NullPool)
        try:
            async with engine.connect() as connection:
                return await connection.run_sync(
                    lambda sync: compare_metadata(MigrationContext.configure(sync), Base.metadata)
                )
        finally:
            await engine.dispose()

    diff = asyncio.run(compare())

    assert diff == [], f"modelos e migrations divergem: {diff}"
