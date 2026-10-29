from datetime import UTC, datetime
from typing import cast

import jwt
from jwt import InvalidTokenError
from sqlalchemy import CursorResult, delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.token_blacklist import TokenBlacklist

# Linhas vencidas apagadas por revogação. A tabela só cresce quando há revogação, então limpar
# nela mantém o tamanho limitado sem agendador; um lote pequeno limita o custo do logout.
_PURGE_BATCH_SIZE = 100


async def purge_expired_tokens(db: AsyncSession, limit: int = _PURGE_BATCH_SIZE) -> int:
    """
    Apaga até `limit` revogações já vencidas e devolve quantas foram. `SKIP LOCKED` faz
    requisições simultâneas pegarem lotes diferentes, sem esperar uma pela outra.
    Quem chama é responsável pelo commit.
    """
    expired = (
        select(TokenBlacklist.id)
        .where(TokenBlacklist.expires_at < func.now())
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    result = await db.execute(delete(TokenBlacklist).where(TokenBlacklist.id.in_(expired)))
    return cast(CursorResult, result).rowcount


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
    await purge_expired_tokens(db)


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
    revoked_now = result.first() is not None
    await purge_expired_tokens(db)
    return expires_at if revoked_now else None
