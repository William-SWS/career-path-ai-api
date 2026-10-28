import hashlib
import hmac
import uuid
from datetime import UTC, datetime, timedelta
from enum import Enum

import jwt
from jwt import InvalidTokenError
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.token_blacklist import TokenBlacklist

bcrypt_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class TokenType(str, Enum):
    """Claim `type`: impede que um tipo de token seja aceito no lugar de outro."""

    ACCESS = "access"
    REFRESH = "refresh"
    RESET_PASSWORD = "reset_password"


_DEFAULT_DURATIONS = {
    TokenType.ACCESS: lambda: timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    TokenType.REFRESH: lambda: timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
}


def password_fingerprint(password_hash: str) -> str:
    """HMAC do hash da senha: muda quando a senha muda e não revela o hash."""
    return hmac.new(
        settings.SECRET_KEY.encode(), password_hash.encode(), hashlib.sha256
    ).hexdigest()[:32]


def create_token(
    user_id: int,
    password_hash: str,
    token_type: TokenType = TokenType.ACCESS,
    token_duration: timedelta | None = None,
) -> str:
    """
    Emite um access ou refresh token; o de reset de senha tem criador próprio.

    O token carrega a impressão da senha atual (claim `pwd`): ao trocar a senha, todo token
    emitido antes deixa de valer, sem precisar guardar estado.
    """
    token_duration = token_duration or _DEFAULT_DURATIONS[token_type]()
    dict_info = {
        "sub": str(user_id),
        "type": token_type.value,
        "pwd": password_fingerprint(password_hash),
        "jti": uuid.uuid4().hex,  # identifica o token; a blacklist guarda só isto
        "exp": datetime.now(UTC) + token_duration,
    }
    encoded_jwt = jwt.encode(dict_info, settings.SECRET_KEY, settings.ALGORITHM)
    return encoded_jwt


def _revocation_claims(token: str) -> tuple[str, datetime] | None:
    """(jti, expiração) de um token válido; None se ele for inválido, expirado ou sem `jti`."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return str(payload["jti"]), datetime.fromtimestamp(payload["exp"], tz=UTC)
    except (InvalidTokenError, KeyError):
        return None


async def is_token_blacklisted(token: str, db: AsyncSession) -> bool:
    """
    Verifica se o token foi revogado. Um token inválido ou expirado não está "revogado": ele
    já é recusado pela validação, antes desta consulta.
    """
    claims = _revocation_claims(token)
    if claims is None:
        return False
    result = await db.execute(select(TokenBlacklist.id).where(TokenBlacklist.jti == claims[0]))
    return result.first() is not None


async def add_token_to_blacklist(token: str, db: AsyncSession) -> None:
    """
    Revoga o token, guardando só o `jti` até a expiração dele. Um token inválido ou já
    expirado não precisa de revogação e é ignorado. Quem chama é responsável pelo commit.
    """
    claims = _revocation_claims(token)
    if claims is None:
        return

    db.add(TokenBlacklist(jti=claims[0], expires_at=claims[1]))
    await db.flush()


async def revoke_token_once(token: str, db: AsyncSession) -> datetime | None:
    """
    Revoga o token de forma atômica e devolve a expiração dele, ou None se ele não pôde ser
    revogado agora (inválido, expirado ou já revogado, inclusive por outra requisição
    simultânea). `INSERT ... ON CONFLICT DO NOTHING` decide a corrida no banco: de duas
    chamadas com o mesmo token, só uma recebe a expiração. Quem chama faz o commit.
    """
    claims = _revocation_claims(token)
    if claims is None:
        return None

    jti, expires_at = claims
    result = await db.execute(
        pg_insert(TokenBlacklist)
        .values(jti=jti, expires_at=expires_at)
        .on_conflict_do_nothing(index_elements=["jti"])
        .returning(TokenBlacklist.id)
    )
    return expires_at if result.first() is not None else None
