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

# Depois de uma falha do storage, não o consultamos por este tempo. Sem isso, cada requisição
# esperaria os timeouts do Redis (medido: ~3 s) durante toda a queda.
_STORAGE_COOLDOWN_SECONDS = 10


class RateLimiter:
    def __init__(self, storage, clock=time.monotonic):
        self._strategy = MovingWindowRateLimiter(storage)
        self._clock = clock
        self._unavailable_until = 0.0

    async def hit(self, namespace: str, limit: str, key: str, *, fail_closed: bool = False) -> None:
        """Conta uma requisição; levanta RateLimitException se o limite foi atingido.

        Redis indisponível: com `fail_closed` recusa a operação (503); sem ele deixa passar
        e registra o erro, para que uma falha do Redis não derrube o login.
        """
        item = parse_limit(limit)
        if self._clock() < self._unavailable_until:
            return self._storage_down(namespace, fail_closed)
        try:
            allowed = await self._strategy.hit(item, namespace, key)
            if allowed:
                return
            reset_time = (await self._strategy.get_window_stats(item, namespace, key)).reset_time
        except StorageError:
            self._unavailable_until = self._clock() + _STORAGE_COOLDOWN_SECONDS
            logger.exception(
                "Rate limiter indisponível (%s); sem consultar por %ss", namespace, _STORAGE_COOLDOWN_SECONDS
            )
            return self._storage_down(namespace, fail_closed)

        retry_after = max(1, math.ceil(reset_time - time.time()))
        logger.warning("Limite excedido (%s)", namespace)
        raise RateLimitException(
            "Muitas requisições. Tente novamente em alguns instantes.",
            code="rate_limit_exceeded",
            headers={"Retry-After": str(retry_after)},
        )

    @staticmethod
    def _storage_down(namespace: str, fail_closed: bool) -> None:
        if fail_closed:
            raise ServiceUnavailableException(
                "Serviço temporariamente indisponível. Tente novamente em instantes.",
                code="rate_limiter_unavailable",
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
