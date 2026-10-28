"""Rate limit: política por rota, chaves, falha do Redis e resposta 429 no envelope padrão."""
import asyncio
import hashlib

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from limits.errors import StorageError
from limits.aio.storage import MemoryStorage
from limits.storage import storage_from_string

from app.api.v1.dependencies.rate_limit import (
    client_ip, limit_ai_generation, limit_login, limit_register,
)
from app.api.v1.dependencies.security import verify_token
from app.core.config import settings
from app.core.exception_handlers import register_exception_handlers
from app.core.exceptions import RateLimitException, ServiceUnavailableException
from app.core.rate_limit import RateLimiter, get_rate_limiter


def memory_limiter():
    return RateLimiter(storage_from_string("async+memory://"))


class BrokenStorage(MemoryStorage):
    """Simula o Redis fora do ar: as operações da janela móvel levantam StorageError."""

    calls = 0

    async def acquire_entry(self, *args, **kwargs):
        self.calls += 1
        raise StorageError(ConnectionError("redis down"))

    async def get_moving_window(self, *args, **kwargs):
        raise StorageError(ConnectionError("redis down"))


def run(coro):
    return asyncio.run(coro)


# ---------- RateLimiter ----------

def test_allows_up_to_the_limit_then_blocks_with_retry_after():
    limiter = memory_limiter()

    async def scenario():
        for _ in range(3):
            await limiter.hit("ns", "3/minute", "k")
        with pytest.raises(RateLimitException) as exc_info:
            await limiter.hit("ns", "3/minute", "k")
        return exc_info.value

    exc = run(scenario())

    assert exc.code == "rate_limit_exceeded" and exc.status_code == 429
    assert 1 <= int(exc.headers["Retry-After"]) <= 60


def test_keys_and_namespaces_are_independent():
    limiter = memory_limiter()

    async def scenario():
        await limiter.hit("login", "1/minute", "ip-a")
        await limiter.hit("login", "1/minute", "ip-b")       # outra chave
        await limiter.hit("register", "1/minute", "ip-a")    # outro namespace
        with pytest.raises(RateLimitException):
            await limiter.hit("login", "1/minute", "ip-a")

    run(scenario())


def test_storage_failure_fails_open_by_default():
    run(RateLimiter(BrokenStorage()).hit("login", "1/minute", "k"))  # não levanta


def test_storage_failure_fails_closed_when_requested():
    with pytest.raises(ServiceUnavailableException) as exc_info:
        run(RateLimiter(BrokenStorage()).hit("ai", "1/minute", "k", fail_closed=True))

    assert exc_info.value.status_code == 503 and exc_info.value.code == "rate_limiter_unavailable"


def test_after_a_storage_failure_it_stops_asking_storage_until_the_cooldown_ends():
    now = [100.0]
    storage = BrokenStorage()
    limiter = RateLimiter(storage, clock=lambda: now[0])

    async def hits(n):
        for _ in range(n):
            await limiter.hit("login", "1/minute", "k")

    run(hits(5))
    assert storage.calls == 1          # só a primeira requisição pagou o timeout

    now[0] += 11                       # passou o cooldown: tenta o storage de novo
    run(hits(2))
    assert storage.calls == 2


def test_fail_closed_keeps_refusing_during_the_cooldown_without_calling_storage():
    storage = BrokenStorage()
    limiter = RateLimiter(storage, clock=lambda: 100.0)

    for _ in range(3):
        with pytest.raises(ServiceUnavailableException):
            run(limiter.hit("ai", "1/minute", "k", fail_closed=True))

    assert storage.calls == 1


def test_storage_recovery_is_noticed_after_the_cooldown():
    now = [0.0]
    limiter = RateLimiter(BrokenStorage(), clock=lambda: now[0])
    run(limiter.hit("login", "1/minute", "k"))                       # falha, abre o cooldown
    limiter._strategy = memory_limiter()._strategy                    # o Redis "voltou"

    now[0] += 11
    run(limiter.hit("login", "1/minute", "k"))
    with pytest.raises(RateLimitException):                           # e o limite volta a valer
        run(limiter.hit("login", "1/minute", "k"))


# ---------- IP do cliente ----------

class FakeRequest:
    def __init__(self, peer="10.0.0.1", forwarded=None):
        self.client = type("C", (), {"host": peer})()
        self.headers = {"x-forwarded-for": forwarded} if forwarded else {}


def test_forwarded_header_is_ignored_without_trusted_proxies(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXY_COUNT", 0)

    assert client_ip(FakeRequest(forwarded="6.6.6.6")) == "10.0.0.1"


def test_with_one_trusted_proxy_the_last_hop_is_the_client_and_spoofing_is_ignored(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXY_COUNT", 1)

    # O cliente forjou "6.6.6.6"; o proxy acrescentou o IP real ao final.
    assert client_ip(FakeRequest(forwarded="6.6.6.6, 203.0.113.9")) == "203.0.113.9"


def test_with_two_trusted_proxies_the_second_from_the_end_is_the_client(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXY_COUNT", 2)

    assert client_ip(FakeRequest(forwarded="6.6.6.6, 203.0.113.9, 172.16.0.5")) == "203.0.113.9"


def test_short_forwarded_header_falls_back_to_the_peer(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXY_COUNT", 2)

    assert client_ip(FakeRequest(forwarded="203.0.113.9")) == "10.0.0.1"


# ---------- dependências em uma app mínima ----------

@pytest.fixture
def mini_app(monkeypatch):
    limiter = memory_limiter()
    app = FastAPI()
    register_exception_handlers(app)
    app.dependency_overrides[get_rate_limiter] = lambda: limiter

    @app.post("/register", dependencies=[Depends(limit_register)])
    async def register():
        return {"ok": True}

    @app.post("/login", dependencies=[Depends(limit_login)])
    async def login(payload: dict):
        return payload

    @app.post("/generate", dependencies=[Depends(limit_ai_generation)])
    async def generate():
        return {"ok": True}

    app.dependency_overrides[verify_token] = lambda: type("U", (), {"id": 1})()
    return app, limiter


def test_over_limit_returns_429_in_the_standard_envelope(mini_app, monkeypatch):
    app, _ = mini_app
    monkeypatch.setattr(settings, "RATE_LIMIT_REGISTER", "2/minute")
    client = TestClient(app)

    statuses = [client.post("/register").status_code for _ in range(3)]
    blocked = client.post("/register")

    assert statuses == [200, 200, 429]
    assert blocked.json()["error"]["code"] == "rate_limit_exceeded"
    assert blocked.json()["error"]["status"] == 429
    assert int(blocked.headers["Retry-After"]) >= 1


def test_login_limit_is_per_account_not_per_ip(mini_app, monkeypatch):
    app, _ = mini_app
    monkeypatch.setattr(settings, "RATE_LIMIT_LOGIN", "2/minute")
    client = TestClient(app)

    for _ in range(2):
        assert client.post("/login", json={"email": "a@example.com"}).status_code == 200

    assert client.post("/login", json={"email": "A@Example.com "}).status_code == 429  # mesma conta
    assert client.post("/login", json={"email": "b@example.com"}).status_code == 200   # outra conta, mesmo IP


def test_login_body_is_still_delivered_to_the_route_after_the_limiter_reads_it(mini_app):
    app, _ = mini_app

    assert TestClient(app).post("/login", json={"email": "a@example.com", "x": 1}).json() == {"email": "a@example.com", "x": 1}


def test_login_limiter_ignores_a_broken_body_instead_of_failing(mini_app):
    app, _ = mini_app

    response = TestClient(app).post("/login", content="not json", headers={"content-type": "application/json"})

    assert response.status_code == 422  # a validação do corpo continua mandando


def test_email_never_appears_in_the_limiter_key(monkeypatch):
    seen = []

    class SpyLimiter:
        async def hit(self, namespace, limit, key, **kwargs):
            seen.append(key)

    class Req(FakeRequest):
        async def json(self):
            return {"email": "Maria@Example.com"}

    run(limit_login(Req(), SpyLimiter()))

    assert "maria" not in seen[0].lower()
    assert seen[0].endswith(hashlib.sha256(b"maria@example.com").hexdigest()[:16])


def test_ai_generation_has_user_burst_hourly_and_global_limits(mini_app, monkeypatch):
    app, _ = mini_app
    monkeypatch.setattr(settings, "RATE_LIMIT_AI_USER_BURST", "2/minute")
    monkeypatch.setattr(settings, "RATE_LIMIT_AI_USER_HOURLY", "100/hour")
    client = TestClient(app)

    assert [client.post("/generate").status_code for _ in range(3)] == [200, 200, 429]


def test_ai_global_ceiling_applies_across_users(mini_app, monkeypatch):
    app, _ = mini_app
    monkeypatch.setattr(settings, "RATE_LIMIT_AI_GLOBAL", "2/minute")
    client = TestClient(app)
    statuses = []
    for user_id in (1, 2, 3):
        app.dependency_overrides[verify_token] = lambda uid=user_id: type("U", (), {"id": uid})()
        statuses.append(client.post("/generate").status_code)

    assert statuses == [200, 200, 429]


def test_ai_generation_fails_closed_when_the_limiter_storage_is_down(mini_app):
    app, _ = mini_app
    app.dependency_overrides[get_rate_limiter] = lambda: RateLimiter(BrokenStorage())

    response = TestClient(app).post("/generate")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "rate_limiter_unavailable"


def test_register_fails_open_when_the_limiter_storage_is_down(mini_app):
    app, _ = mini_app
    app.dependency_overrides[get_rate_limiter] = lambda: RateLimiter(BrokenStorage())

    assert TestClient(app).post("/register").status_code == 200


# ---------- configuração ----------

@pytest.mark.parametrize("bad", ["", "5", "five/minute", "5/fortnight", "0/minute"])
def test_invalid_limit_strings_are_rejected_at_startup(bad):
    from pydantic import ValidationError
    from app.core.config import Settings

    with pytest.raises(ValidationError):
        Settings(RATE_LIMIT_LOGIN=bad)
