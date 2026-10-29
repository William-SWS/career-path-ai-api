import asyncio

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import settings
from app.core.database import async_engine
from app.core.logging_config import logger
from app.core.rate_limit import RateLimiter, get_rate_limiter

router = APIRouter(tags=["health"])

# Uma sonda lenta não pode pendurar o orquestrador: passou disso, a dependência conta como fora.
_CHECK_TIMEOUT_SECONDS = 2


@router.get("/health")
async def health():
    """Liveness: o processo responde. Não consulta dependências, para que uma queda delas
    não faça o orquestrador reiniciar uma API que está de pé."""
    return {"status": "ok"}


async def _postgres_status() -> str:
    try:
        async with asyncio.timeout(_CHECK_TIMEOUT_SECONDS):
            async with async_engine.connect() as connection:
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


@router.get("/ready")
async def ready(limiter: RateLimiter = Depends(get_rate_limiter)):
    """Readiness: a API consegue atender. Sem o Postgres, 503. Sem o Redis, 200 "degraded":
    só a geração com IA depende dele (e já responde 503 por conta própria); tirar a API
    inteira de rotação derrubaria também o login, que funciona sem ele."""
    postgres, redis = await asyncio.gather(_postgres_status(), _redis_status(limiter))
    checks = {"postgres": postgres, "redis": redis}

    if postgres == "down":
        status, http_status = "unavailable", 503
    elif redis == "down":
        status, http_status = "degraded", 200
    else:
        status, http_status = "ok", 200
    return JSONResponse({"status": status, "checks": checks}, status_code=http_status)
