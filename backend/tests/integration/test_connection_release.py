"""A espera pelo LLM (segundos) não pode segurar uma conexão do pool de banco."""
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.database import get_db
from app.llm.client import get_llm_client
from app.main import app
from app.schemas.ai_outputs import DevelopmentTrailOutput
from tests.fakes import sample_output
from tests.integration.conftest import API, CREDENTIALS, bearer

pytestmark = pytest.mark.integration

TRAIL = {"name": "Ana", "skills": ["Python"], "professional_goal": "Back-End"}
VALID_JSON = json.dumps(sample_output(DevelopmentTrailOutput))


class SlowLLM:
    """Simula o Gemini: demora e registra quantas conexões do pool estavam em uso durante a espera."""

    def __init__(self, engine, delay=0.0):
        self.engine = engine
        self.delay = delay
        self.checked_out_during_call = []

    async def generate(self, prompt, params, response_schema=None):
        self.checked_out_during_call.append(self.engine.pool.checkedout())
        await asyncio.sleep(self.delay)
        return VALID_JSON


@pytest.fixture
def tiny_pool_client():
    """App com um pool de UMA conexão e pouca paciência: qualquer conexão presa aparece como erro."""
    engine = create_async_engine(
        settings.DATABASE_URI, pool_size=1, max_overflow=0, pool_timeout=0.5
    )
    maker = async_sessionmaker(engine, class_=AsyncSession, autoflush=False)

    async def session_per_request():
        async with maker() as session:
            yield session

    app.dependency_overrides[get_db] = session_per_request
    with TestClient(app) as client:
        yield client, engine
    app.dependency_overrides.clear()
    asyncio.run(engine.dispose())


def login(client):
    client.post(f"{API}/auth/register", json={"name": "Maria Silva", **CREDENTIALS})
    return bearer(client.post(f"{API}/auth/login", json=CREDENTIALS).json()["tokens"]["access_token"])


def test_no_connection_is_held_while_waiting_for_the_llm(tiny_pool_client):
    client, engine = tiny_pool_client
    llm = SlowLLM(engine)
    app.dependency_overrides[get_llm_client] = lambda: llm

    response = client.post(f"{API}/development-trail/", json=TRAIL, headers=login(client))

    assert response.status_code == 200
    assert llm.checked_out_during_call == [0]


def test_concurrent_generations_do_not_starve_the_pool(tiny_pool_client):
    client, engine = tiny_pool_client
    app.dependency_overrides[get_llm_client] = lambda: SlowLLM(engine, delay=1.5)
    headers = login(client)

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(client.post, f"{API}/development-trail/", json=TRAIL, headers=headers) for _ in range(3)]
        statuses = [f.result().status_code for f in futures]

    assert statuses == [200, 200, 200]
    assert client.get(f"{API}/development-trail/", headers=headers).json()["total_count"] == 3
