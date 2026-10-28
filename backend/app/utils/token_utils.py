import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from typing import NamedTuple

from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import TokenType
from app.models.token_blacklist import TokenBlacklist


def cleanup_expired_tokens(db: Session) -> int:
    """
    Remove tokens expirados da blacklist. Quem chama é responsável pelo commit.
    """
    now = datetime.now(UTC)
    deleted_count = db.query(TokenBlacklist).filter(TokenBlacklist.expires_at < now).delete()
    return deleted_count


def decode_jwt_token(token: str, expected_type: TokenType) -> dict:
    """Levanta JWTError se o token for inválido, estiver expirado ou for de outro tipo."""
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

    if payload.get("type") != expected_type.value:
        raise JWTError(f"Esperado token do tipo {expected_type.value}")

    return payload


def get_token_subject(token: str, expected_type: TokenType) -> str | None:
    """Subject do token, ou None se ele for inválido, expirado ou de outro tipo."""
    try:
        return decode_jwt_token(token, expected_type).get("sub")
    except JWTError:
        return None


def password_fingerprint(password_hash: str) -> str:
    """HMAC do hash da senha: muda quando a senha muda e não revela o hash."""
    return hmac.new(
        settings.SECRET_KEY.encode(), password_hash.encode(), hashlib.sha256
    ).hexdigest()[:32]


def create_reset_password_token(email: str, password_hash: str) -> str:
    """
    Cria um token JWT para reset de senha. Ele carrega a impressão digital da
    senha atual (claim `pwd`), então deixa de valer assim que a senha muda:
    uso único, sem precisar guardar estado.
    """
    expire = datetime.now(UTC) + timedelta(hours=settings.RESET_PASSWORD_TOKEN_EXPIRE_HOURS)

    to_encode = {
        "sub": email,
        "exp": expire,
        "type": TokenType.RESET_PASSWORD.value,
        "pwd": password_fingerprint(password_hash),
    }

    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


class ResetTokenClaims(NamedTuple):
    email: str
    password_fingerprint: str


def read_reset_password_token(token: str) -> ResetTokenClaims | None:
    """Claims do token de reset, ou None se ele for inválido, expirado ou legado (sem `pwd`)."""
    try:
        payload = decode_jwt_token(token, TokenType.RESET_PASSWORD)
    except JWTError:
        return None

    email, fingerprint = payload.get("sub"), payload.get("pwd")
    if not email or not fingerprint:
        return None

    return ResetTokenClaims(email, fingerprint)


def reset_token_matches_password(claims: ResetTokenClaims, password_hash: str) -> bool:
    return hmac.compare_digest(claims.password_fingerprint, password_fingerprint(password_hash))
