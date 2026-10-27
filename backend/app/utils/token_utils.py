from app.models.token_blacklist import TokenBlacklist
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from jose import jwt, JWTError
from app.core.config import settings
from app.core.security import TokenType
from typing import Optional


def cleanup_expired_tokens(db: Session) -> int:
    """
    Remove tokens expirados da blacklist. Quem chama é responsável pelo commit.
    """
    now = datetime.now(timezone.utc)
    deleted_count = db.query(TokenBlacklist).filter(
        TokenBlacklist.expires_at < now
    ).delete()
    return deleted_count


def decode_jwt_token(token: str, expected_type: TokenType) -> dict:
    """Levanta JWTError se o token for inválido, estiver expirado ou for de outro tipo."""
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

    if payload.get("type") != expected_type.value:
        raise JWTError(f"Esperado token do tipo {expected_type.value}")

    return payload


def get_token_subject(token: str, expected_type: TokenType) -> Optional[str]:
    """Subject do token, ou None se ele for inválido, expirado ou de outro tipo."""
    try:
        return decode_jwt_token(token, expected_type).get("sub")
    except JWTError:
        return None


def create_reset_password_token(email: str) -> str:
    """
    Cria um token JWT para reset de senha
    """
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.RESET_PASSWORD_TOKEN_EXPIRE_HOURS)

    to_encode = {
        "sub": email,
        "exp": expire,
        "type": TokenType.RESET_PASSWORD.value
    }

    encoded_jwt = jwt.encode(
        to_encode, 
        settings.SECRET_KEY, 
        algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def verify_reset_password_token(token: str) -> Optional[str]:
    """
    Verifica e decodifica um token de reset de senha
    Retorna o email se o token for válido, None caso contrário
    """
    return get_token_subject(token, TokenType.RESET_PASSWORD)
