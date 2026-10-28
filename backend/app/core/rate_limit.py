"""Limite de requisições: janela móvel sobre Redis (ou memória, em desenvolvimento).

Estourar o limite vira 429 no envelope de erro padrão, com `Retry-After`. As políticas
por rota (chaves e valores) ficam em api/v1/dependencies/rate_limit.py.
"""
import math
import time
from functools import lru_cache

from limits import parse as parse_limit
from limits.aio.strategies import MovingWindowRateLimiter
from limits.errors import StorageError
from limits.storage import storage_from_string

from app.core.config import settings
from app.core.exceptions import RateLimitException, ServiceUnavailableException
from app.core.logging_config import logger


class RateLimiter:
    def __init__(self, storage):
        self._strategy = MovingWindowRateLimiter(storage)

    async def hit(self, namespace: str, limit: str, key: str, *, fail_closed: bool = False) -> None:
        """Conta uma requisição; levanta RateLimitException se o limite foi atingido.

        Redis indisponível: com `fail_closed` recusa a operação (503); sem ele deixa passar
        e registra o erro, para que uma falha do Redis não derrube o login.
        """
        item = parse_limit(limit)
        try:
            allowed = await self._strategy.hit(item, namespace, key)
            if allowed:
                return
            reset_time = (await self._strategy.get_window_stats(item, namespace, key)).reset_time
        except StorageError:
            logger.exception("Rate limiter indisponível (%s, fail_closed=%s)", namespace, fail_closed)
            if fail_closed:
                raise ServiceUnavailableException(
                    "Serviço temporariamente indisponível. Tente novamente em instantes.",
                    code="rate_limiter_unavailable",
                )
            return

        retry_after = max(1, math.ceil(reset_time - time.time()))
        logger.warning("Limite excedido (%s)", namespace)
        raise RateLimitException(
            "Muitas requisições. Tente novamente em alguns instantes.",
            code="rate_limit_exceeded",
            headers={"Retry-After": str(retry_after)},
        )


def build_rate_limiter(redis_url: str) -> RateLimiter:
    if redis_url:
        # `limits` usa o prefixo "async+" para o cliente assíncrono. Timeouts curtos:
        # um Redis lento não pode atrasar cada requisição.
        uri = "async+" + redis_url.removeprefix("async+")
        storage = storage_from_string(uri, wrap_exceptions=True, connect_timeout=1, stream_timeout=1)
    else:
        logger.warning("REDIS_URL não definido: rate limit em memória, válido só para desenvolvimento")
        storage = storage_from_string("async+memory://")
    return RateLimiter(storage)


@lru_cache
def get_rate_limiter() -> RateLimiter:
    return build_rate_limiter(settings.REDIS_URL)
