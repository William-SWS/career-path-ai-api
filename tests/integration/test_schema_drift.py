"""O schema que as migrations constroem tem que ser o que os modelos declaram."""

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine

import app.models  # noqa: F401  (registra as tabelas no metadata)
from app.core.config import settings
from app.core.database import Base

pytestmark = pytest.mark.integration


def test_migrations_and_models_have_no_drift():
    engine = create_engine(settings.DATABASE_URI.replace("postgresql+asyncpg://", "postgresql://"))
    try:
        with engine.connect() as connection:
            diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    finally:
        engine.dispose()

    assert diff == [], f"modelos e migrations divergem: {diff}"
