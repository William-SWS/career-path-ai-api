from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError

from app.api.v1.dependencies.database import get_db
from app.core.config import settings
from app.core.security import TokenType, is_token_blacklisted
from app.models.user import User
from app.repository.user_repository import UserRepository
from app.utils.token_utils import decode_jwt_token


oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login-form")


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=401, detail=detail, headers={"WWW-Authenticate": "Bearer"}
    )


async def _authenticate(token: str, token_type: TokenType, db: AsyncSession) -> User:
    # Valida assinatura, expiração e tipo antes de qualquer acesso ao banco.
    try:
        user_id = int(decode_jwt_token(token, token_type)["sub"])
    except (JWTError, KeyError, ValueError):
        raise _unauthorized("Token é inválido ou está expirado")

    if await is_token_blacklisted(token, db):
        raise _unauthorized("Token revogado")

    user = await UserRepository(db).get_by_id(user_id)
    if user is None:
        raise _unauthorized("Não foi possível validar as credenciais")

    return user


async def verify_token(
    token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)
) -> User:
    """Autentica uma requisição por access token."""
    return await _authenticate(token, TokenType.ACCESS, db)


async def verify_refresh_token(
    token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)
) -> User:
    """Autentica a renovação de sessão: só aceita refresh token válido e não expirado."""
    return await _authenticate(token, TokenType.REFRESH, db)
