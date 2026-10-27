from app.models.token_blacklist import TokenBlacklist
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from jose import jwt, JWTError
from app.core.config import settings
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


def decode_jwt_token(token: str) -> dict:
    """Levanta JWTError se o token for inválido ou estiver expirado."""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


def create_reset_password_token(email: str) -> str:
    """
    Cria um token JWT para reset de senha
    """
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.RESET_PASSWORD_TOKEN_EXPIRE_HOURS)

    to_encode = {
        "sub": email,
        "exp": expire,
        "type": "reset_password"
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
    try:
        payload = jwt.decode(
            token, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM]
        )
        
        email: str = payload.get("sub")
        token_type: str = payload.get("type")
        
        if email is None or token_type != "reset_password":
            return None
            
        return email
    except JWTError:
        return None
