import asyncio
import os
import subprocess
import sys
from contextlib import asynccontextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.database import get_db
from app.main import app

pytestmark = pytest.mark.integration

_TABLES = "users, token_blacklist, development_trails, interview_guide, resume_analyses"


def pytest_collection_modifyitems(config, items):
    if os.environ.get("TEST_DATABASE_URL"):
        return
    skip = pytest.mark.skip(reason="defina TEST_DATABASE_URL para rodar os testes de integração")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(scope="session", autouse=True)
def migrated_database():
    """Aplica as migrations reais (não create_all), para testar o schema que vai a produção."""
    if not os.environ.get("TEST_DATABASE_URL"):
        return
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "heads"], check=True, capture_output=True
    )


@pytest.fixture(autouse=True)
def clean_tables(migrated_database):
    if not os.environ.get("TEST_DATABASE_URL"):
        return

    async def truncate():
        engine = create_async_engine(settings.DATABASE_URI, poolclass=NullPool)
        async with engine.begin() as conn:
            await conn.execute(text(f"TRUNCATE {_TABLES} RESTART IDENTITY CASCADE"))
        await engine.dispose()

    asyncio.run(truncate())


@asynccontextmanager
async def open_sessions():
    """Fábrica de sessões independentes, como duas requisições concorrentes."""
    # Mesmas opções do app (core/database.py), mas sem pool: cada teste roda em
    # seu próprio event loop.
    engine = create_async_engine(settings.DATABASE_URI, poolclass=NullPool)
    try:
        yield async_sessionmaker(engine, class_=AsyncSession, autoflush=False)
    finally:
        await engine.dispose()


API = "/api/v1"
CREDENTIALS = {"email": "maria@example.com", "password": "Abcdef12"}


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def http():
    # Uma sessão por requisição, sem pool: o TestClient roda em outro event loop.
    engine = create_async_engine(settings.DATABASE_URI, poolclass=NullPool)
    maker = async_sessionmaker(engine, class_=AsyncSession, autoflush=False)

    async def session_per_request():
        async with maker() as session:
            yield session

    app.dependency_overrides[get_db] = session_per_request
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def session_tokens(http):
    http.post(f"{API}/auth/register", json={"name": "Maria Silva", **CREDENTIALS})
    return http.post(f"{API}/auth/login", json=CREDENTIALS).json()["tokens"]
