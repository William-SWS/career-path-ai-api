"""/ready contra Postgres e Redis de verdade (os testes de tests/test_health.py usam simulações)."""

import asyncio
import os

import httpx
import pytest
from sqlalchemy.engine import make_url
from sqlalchemy.exc import TimeoutError as PoolTimeoutError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.api.v1.routes import health_routes
from app.core.config import settings
from app.core.database import async_engine
from app.core.rate_limit import build_rate_limiter, get_rate_limiter
from app.main import app

pytestmark = pytest.mark.integration

REDIS_URL = os.getenv("REDIS_TEST_URL")
UNREACHABLE_REDIS_URL = "redis://127.0.0.1:1/0"  # porta sem ninguém ouvindo


@pytest.fixture
def probe(http, monkeypatch):
    """Aponta o /ready para o Postgres e o Redis informados; o padrão são os de teste."""

    def configure(*, redis_url=REDIS_URL, port=None):
        uri = make_url(settings.DATABASE_URI)
        if port is not None:
            uri = uri.set(port=port)
        # Sem pool, como os demais testes: o TestClient roda em outro event loop.
        monkeypatch.setattr(
            health_routes, "probe_engine", create_async_engine(uri, poolclass=NullPool)
        )
        monkeypatch.setattr(settings, "REDIS_URL", redis_url or "")
        app.dependency_overrides[get_rate_limiter] = lambda: build_rate_limiter(redis_url or "")
        return http

    return configure


@pytest.mark.skipif(not REDIS_URL, reason="defina REDIS_TEST_URL para testar com Redis real")
def test_ready_is_ok_with_real_postgres_and_redis(probe):
    response = probe().get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {"postgres": "ok", "redis": "ok"}}


def test_ready_is_degraded_when_redis_is_unreachable(probe):
    response = probe(redis_url=UNREACHABLE_REDIS_URL).get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "degraded", "checks": {"postgres": "ok", "redis": "down"}}


def test_ready_is_unavailable_when_postgres_is_unreachable(probe):
    response = probe(redis_url="", port=1).get("/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "unavailable",
        "checks": {"postgres": "down", "redis": "skipped"},
    }


def _ready_with_traffic_pool_exhausted(monkeypatch, shared_pool: bool):
    """Esgota o pool real do tráfego (`async_engine`) e chama /ready, no mesmo event loop."""
    monkeypatch.setattr(settings, "REDIS_URL", "")
    # Com o pool cheio, a espera por conexão falha rápido.
    monkeypatch.setattr(async_engine.pool, "_timeout", 0.5)
    capacity = async_engine.pool.size() + async_engine.pool._max_overflow  # type: ignore[attr-defined]

    async def scenario():
        held = [await async_engine.connect() for _ in range(capacity)]
        try:
            # Prova que o pool está mesmo esgotado: mais uma conexão estoura o timeout.
            with pytest.raises(PoolTimeoutError):
                await async_engine.connect()

            if shared_pool:
                monkeypatch.setattr(health_routes, "probe_engine", async_engine)
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                return await client.get("/ready")
        finally:
            for connection in held:
                await connection.close()
            await async_engine.dispose()
            await health_routes.probe_engine.dispose()

    return asyncio.run(scenario())


def test_ready_stays_ok_while_the_traffic_pool_is_exhausted(monkeypatch):
    """O motivo do engine próprio do /ready: carga que esgota o pool não pode virar 503."""
    response = _ready_with_traffic_pool_exhausted(monkeypatch, shared_pool=False)

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {"postgres": "ok", "redis": "skipped"}}


def test_ready_would_fail_if_it_shared_the_exhausted_traffic_pool(monkeypatch):
    """Contraprova: o mesmo cenário, com o /ready no pool do tráfego, vira 503. Sem ela, o teste
    acima passaria também se o esgotamento nunca atrapalhasse ninguém."""
    response = _ready_with_traffic_pool_exhausted(monkeypatch, shared_pool=True)

    assert response.status_code == 503
    assert response.json()["checks"]["postgres"] == "down"
