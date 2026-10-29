import asyncio
import time
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import settings
from app.core.database import probe_engine
from app.core.logging_config import logger
from app.core.rate_limit import RateLimiter, get_rate_limiter

router = APIRouter(tags=["health"])

# Uma sonda lenta não pode pendurar o orquestrador: passou disso, a dependência conta como fora.
_CHECK_TIMEOUT_SECONDS = 2

# O resultado vale por este tempo. Sondar mil vezes por segundo vira uma verificação a cada 3 s,
# e uma queda aparece com no máximo esse atraso (um orquestrador sonda a cada 10-15 s).
_CACHE_TTL_SECONDS = 3

ReadinessResult = tuple[int, dict]


class _ReadinessCache:
    """Guarda o último resultado por `ttl` segundos e deixa só uma verificação em andamento:
    quem chega com o cache vencido espera a verificação em curso em vez de abrir outra."""

    def __init__(self, ttl: float, clock: Callable[[], float] = time.monotonic) -> None:
        self._ttl = ttl
        self._clock = clock
        self.clear()

    def clear(self) -> None:
        self._value: ReadinessResult | None = None
        self._expires_at = 0.0
        self._lock = asyncio.Lock()

    def _fresh(self) -> ReadinessResult | None:
        return self._value if self._clock() < self._expires_at else None

    async def get(self, compute: Callable[[], Awaitable[ReadinessResult]]) -> ReadinessResult:
        if (cached := self._fresh()) is not None:
            return cached
        async with self._lock:
            # Quem estava na frente pode ter verificado enquanto esperávamos a trava.
            if (cached := self._fresh()) is not None:
                return cached
            self._value = await compute()
            self._expires_at = self._clock() + self._ttl
            return self._value


readiness_cache = _ReadinessCache(_CACHE_TTL_SECONDS)


@router.get("/health")
async def health():
    """Liveness: o processo responde. Não consulta dependências, para que uma queda delas
    não faça o orquestrador reiniciar uma API que está de pé."""
    return {"status": "ok"}


async def _postgres_status() -> str:
    try:
        async with asyncio.timeout(_CHECK_TIMEOUT_SECONDS):
            async with probe_engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Readiness: Postgres indisponível")
        return "down"
    return "ok"


async def _redis_status(limiter: RateLimiter) -> str:
    if not settings.REDIS_URL:
        return "skipped"
    try:
        async with asyncio.timeout(_CHECK_TIMEOUT_SECONDS):
            available = await limiter.is_available()
    except Exception:
        logger.exception("Readiness: Redis indisponível")
        return "down"
    return "ok" if available else "down"


async def _check_readiness(limiter: RateLimiter) -> ReadinessResult:
    postgres, redis = await asyncio.gather(_postgres_status(), _redis_status(limiter))
    checks = {"postgres": postgres, "redis": redis}

    if postgres == "down":
        status, http_status = "unavailable", 503
    elif redis == "down":
        status, http_status = "degraded", 200
    else:
        status, http_status = "ok", 200
    return http_status, {"status": status, "checks": checks}


@router.get("/ready")
async def ready(limiter: RateLimiter = Depends(get_rate_limiter)):
    """Readiness: a API consegue atender. Sem o Postgres, 503. Sem o Redis, 200 "degraded":
    só a geração com IA depende dele (e já responde 503 por conta própria); tirar a API
    inteira de rotação derrubaria também o login, que funciona sem ele.

    O resultado é guardado por poucos segundos (veja `_ReadinessCache`), então esta rota
    pública não vira um jeito barato de pressionar o banco."""
    http_status, body = await readiness_cache.get(lambda: _check_readiness(limiter))
    return JSONResponse(body, status_code=http_status)
