import asyncio

import httpx
import pytest

from app.api.v1.routes import health_routes
from app.core.rate_limit import get_rate_limiter
from app.main import app


class FakeConnection:
    def __init__(self, error: Exception | None = None, delay: float = 0):
        self.error = error
        self.delay = delay

    async def __aenter__(self):
        await asyncio.sleep(self.delay)
        if self.error:
            raise self.error
        return self

    async def __aexit__(self, *exc):
        return False

    async def execute(self, statement):
        pass


class FakeEngine:
    def __init__(self, **options):
        self.options = options
        self.connects = 0

    def connect(self):
        self.connects += 1
        return FakeConnection(**self.options)


class FakeLimiter:
    def __init__(self, available: bool = True, error: Exception | None = None, delay: float = 0):
        self.available = available
        self.error = error
        self.delay = delay
        self.checks = 0

    async def is_available(self) -> bool:
        self.checks += 1
        await asyncio.sleep(self.delay)
        if self.error:
            raise self.error
        return self.available


@pytest.fixture
def probe(monkeypatch):
    """Configura as dependências que o /ready consulta; o padrão é tudo de pé."""

    def configure(*, postgres=None, redis=None, redis_url="redis://redis:6379/0"):
        monkeypatch.setattr(health_routes, "probe_engine", postgres or FakeEngine())
        monkeypatch.setattr(health_routes.settings, "REDIS_URL", redis_url)
        app.dependency_overrides[get_rate_limiter] = lambda: redis or FakeLimiter()

    yield configure
    app.dependency_overrides.pop(get_rate_limiter, None)


def test_health_reports_ok_without_touching_dependencies(client, monkeypatch):
    monkeypatch.setattr(health_routes, "probe_engine", None)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_ok_when_everything_is_up(client, probe):
    probe()

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {"postgres": "ok", "redis": "ok"}}


def test_ready_is_unavailable_when_postgres_is_down(client, probe):
    probe(postgres=FakeEngine(error=ConnectionRefusedError("boom")))

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "unavailable",
        "checks": {"postgres": "down", "redis": "ok"},
    }


def test_ready_is_degraded_but_200_when_redis_is_down(client, probe):
    probe(redis=FakeLimiter(available=False))

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "degraded", "checks": {"postgres": "ok", "redis": "down"}}


def test_ready_treats_a_redis_error_as_down(client, probe):
    probe(redis=FakeLimiter(error=ConnectionError("boom")))

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json()["checks"]["redis"] == "down"


def test_ready_skips_redis_when_not_configured(client, probe):
    probe(redis=FakeLimiter(available=False), redis_url="")

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {"postgres": "ok", "redis": "skipped"}}


def test_ready_does_not_hang_on_a_slow_dependency(client, probe, monkeypatch):
    monkeypatch.setattr(health_routes, "_CHECK_TIMEOUT_SECONDS", 0.05)
    probe(postgres=FakeEngine(delay=1))

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json()["checks"]["postgres"] == "down"


def test_ready_does_not_leak_error_details(client, probe):
    probe(postgres=FakeEngine(error=ConnectionRefusedError("postgresql://user:secret@db")))

    assert "secret" not in client.get("/ready").text


def test_health_routes_live_outside_the_api_prefix(client):
    schema = client.get("/openapi.json").json()["paths"]

    assert {"/health", "/ready"} <= schema.keys()
    assert "/api/v1/check/" not in schema


def test_ready_reuses_the_last_result_instead_of_probing_every_time(client, probe):
    engine, limiter = FakeEngine(), FakeLimiter()
    probe(postgres=engine, redis=limiter)

    statuses = {client.get("/ready").status_code for _ in range(20)}

    assert statuses == {200}
    assert (engine.connects, limiter.checks) == (1, 1)


def test_ready_probes_again_once_the_result_expires(client, probe, monkeypatch):
    now = [100.0]
    monkeypatch.setattr(health_routes.readiness_cache, "_clock", lambda: now[0])
    engine = FakeEngine()
    probe(postgres=engine)

    client.get("/ready")
    now[0] += health_routes._CACHE_TTL_SECONDS - 0.1
    client.get("/ready")
    assert engine.connects == 1

    now[0] += 0.2
    client.get("/ready")
    assert engine.connects == 2


def test_ready_notices_an_outage_after_the_cached_result_expires(client, probe, monkeypatch):
    now = [100.0]
    monkeypatch.setattr(health_routes.readiness_cache, "_clock", lambda: now[0])
    probe()
    assert client.get("/ready").status_code == 200

    probe(postgres=FakeEngine(error=ConnectionRefusedError("boom")))
    assert client.get("/ready").status_code == 200  # ainda o resultado guardado

    now[0] += health_routes._CACHE_TTL_SECONDS + 0.1
    assert client.get("/ready").status_code == 503


def test_concurrent_ready_calls_share_a_single_probe(probe):
    engine, limiter = FakeEngine(delay=0.2), FakeLimiter(delay=0.2)
    probe(postgres=engine, redis=limiter)

    async def scenario():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            return await asyncio.gather(*(http.get("/ready") for _ in range(30)))

    responses = asyncio.run(scenario())

    assert {response.status_code for response in responses} == {200}
    assert (engine.connects, limiter.checks) == (1, 1)


def test_ready_uses_its_own_single_connection_pool_not_the_traffic_one():
    from app.core.database import async_engine, probe_engine

    assert health_routes.probe_engine is probe_engine
    assert probe_engine is not async_engine
    assert probe_engine.pool.size() == 1  # type: ignore[attr-defined]
    assert probe_engine.pool._max_overflow == 0  # type: ignore[attr-defined]
