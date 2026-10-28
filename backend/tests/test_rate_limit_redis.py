"""Rate limit contra um Redis de verdade (defina REDIS_TEST_URL, ex.: redis://localhost:56379/0)."""

import asyncio
import os
import time
import uuid

import pytest

from app.core.exceptions import RateLimitException
from app.core.rate_limit import build_rate_limiter

REDIS_URL = os.getenv("REDIS_TEST_URL")
pytestmark = pytest.mark.skipif(
    not REDIS_URL, reason="defina REDIS_TEST_URL para testar com Redis real"
)


def redis_limiter(url=None):
    return build_rate_limiter(url or REDIS_URL)


def test_counter_lives_in_redis_and_is_shared_between_limiter_instances():
    key = uuid.uuid4().hex  # isola o teste de execuções anteriores

    async def scenario():
        await redis_limiter().hit("shared", "2/minute", key)
        await redis_limiter().hit("shared", "2/minute", key)  # outra instância, mesmo contador
        with pytest.raises(RateLimitException) as exc_info:
            await redis_limiter().hit("shared", "2/minute", key)
        return exc_info.value

    exc = asyncio.run(scenario())

    assert 1 <= int(exc.headers["Retry-After"]) <= 60


def test_unreachable_redis_fails_open_quickly_instead_of_hanging_every_request():
    limiter = redis_limiter("redis://127.0.0.1:1/0")  # porta sem ninguém ouvindo

    started = time.perf_counter()
    asyncio.run(limiter.hit("login", "1/minute", "k"))  # fail-open: não levanta
    elapsed = time.perf_counter() - started

    assert elapsed < 3


def test_unreachable_redis_fails_closed_for_ai():
    from app.core.exceptions import ServiceUnavailableException

    limiter = redis_limiter("redis://127.0.0.1:1/0")

    with pytest.raises(ServiceUnavailableException):
        asyncio.run(limiter.hit("ai", "1/minute", "k", fail_closed=True))
