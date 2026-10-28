"""Políticas de rate limit por rota, como dependências do FastAPI."""

import hashlib

from fastapi import Depends, Request

from app.api.v1.dependencies.security import verify_token
from app.core.config import settings
from app.core.rate_limit import RateLimiter, get_rate_limiter
from app.models.user import User


def client_ip(request: Request) -> str:
    """IP do cliente. X-Forwarded-For só vale com proxies de confiança configurados."""
    trusted = settings.TRUSTED_PROXY_COUNT
    if trusted > 0:
        hops = [
            h.strip() for h in request.headers.get("x-forwarded-for", "").split(",") if h.strip()
        ]
        # Cada proxy acrescenta o endereço de quem falou com ele: o cliente real é o N-ésimo do fim.
        if len(hops) >= trusted:
            return hops[-trusted]
    return request.client.host if request.client else "unknown"


def _ip_rule(namespace: str, setting_name: str):
    async def dependency(
        request: Request, limiter: RateLimiter = Depends(get_rate_limiter)
    ) -> None:
        await limiter.hit(namespace, getattr(settings, setting_name), client_ip(request))

    return dependency


limit_register = _ip_rule("register", "RATE_LIMIT_REGISTER")
limit_forgot_password = _ip_rule("forgot_password", "RATE_LIMIT_FORGOT_PASSWORD")
limit_reset_password = _ip_rule("reset_password", "RATE_LIMIT_RESET_PASSWORD")
limit_login_form = _ip_rule("login", "RATE_LIMIT_LOGIN")


async def limit_login(request: Request, limiter: RateLimiter = Depends(get_rate_limiter)) -> None:
    """IP + e-mail: frear tentativas contra uma conta sem bloquear quem divide o mesmo IP."""
    key = client_ip(request)
    try:
        email = (await request.json()).get("email")
    except (ValueError, AttributeError):
        email = None  # corpo inválido: o 422 sai depois; aqui vale só o IP
    if isinstance(email, str):
        # Hash: o e-mail não aparece nas chaves do Redis.
        key += ":" + hashlib.sha256(email.strip().lower().encode()).hexdigest()[:16]
    await limiter.hit("login", settings.RATE_LIMIT_LOGIN, key)


async def limit_ai_generation(
    user: User = Depends(verify_token), limiter: RateLimiter = Depends(get_rate_limiter)
) -> None:
    """Geração com IA custa dinheiro e cota: por usuário (hora e rajada) e teto global.

    Fail-closed: sem o limite, um Redis fora do ar deixaria o gasto sem controle.
    """
    await limiter.hit(
        "ai_user_burst", settings.RATE_LIMIT_AI_USER_BURST, str(user.id), fail_closed=True
    )
    await limiter.hit(
        "ai_user_hourly", settings.RATE_LIMIT_AI_USER_HOURLY, str(user.id), fail_closed=True
    )
    await limiter.hit("ai_global", settings.RATE_LIMIT_AI_GLOBAL, "all", fail_closed=True)
