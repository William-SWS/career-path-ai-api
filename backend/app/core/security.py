from app.core.config import settings
from app.models.user import User
from app.models.token_blacklist import TokenBlacklist
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from enum import Enum
import uuid

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


def create_token(
    user_id: int,
    token_type: TokenType = TokenType.ACCESS,
    token_duration: timedelta | None = None,
) -> str:
    """Emite um access ou refresh token; o de reset de senha tem criador próprio."""
    token_duration = token_duration or _DEFAULT_DURATIONS[token_type]()
    dict_info = {
        "sub": str(user_id),
        "type": token_type.value,
        "jti": uuid.uuid4().hex,  # token único: a blacklist guarda a string inteira
        "exp": datetime.now(timezone.utc) + token_duration,
    }
    encoded_jwt = jwt.encode(dict_info, settings.SECRET_KEY, settings.ALGORITHM)
    return encoded_jwt


async def is_token_blacklisted(token: str, db: AsyncSession) -> bool:
    """
    Verifica se o token está na blacklist
    """
    result = await db.execute(select(TokenBlacklist).where(TokenBlacklist.token == token))
    blacklisted_token = result.scalar_one_or_none()
    return blacklisted_token is not None


async def add_token_to_blacklist(token: str, db: AsyncSession):
    """
    Adiciona token à blacklist. Quem chama é responsável pelo commit.
    """
    try:
        # Tenta decodificar o token para pegar a expiração real
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        
    except JWTError:
        # Se o token é inválido ou expirado, usa expiração padrão
        expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    
    db.add(TokenBlacklist(token=token, expires_at=expires_at))
    await db.flush()
