import hmac
import uuid
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import NamedTuple

import jwt
from jwt import InvalidTokenError

from app.core.config import settings
from app.security.passwords import password_fingerprint


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


def decode_jwt_token(token: str, expected_type: TokenType) -> dict:
    """Levanta InvalidTokenError se o token for inválido, estiver expirado ou for de outro tipo."""
    payload = jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
        options={"require": ["exp", "sub"]},  # token sem expiração nunca é aceito
    )

    if payload.get("type") != expected_type.value:
        raise InvalidTokenError(f"Esperado token do tipo {expected_type.value}")

    return payload


def get_token_subject(token: str, expected_type: TokenType) -> str | None:
    """Subject do token, ou None se ele for inválido, expirado ou de outro tipo."""
    try:
        return decode_jwt_token(token, expected_type).get("sub")
    except InvalidTokenError:
        return None


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
    except InvalidTokenError:
        return None

    email, fingerprint = payload.get("sub"), payload.get("pwd")
    if not email or not fingerprint:
        return None

    return ResetTokenClaims(email, fingerprint)


def reset_token_matches_password(claims: ResetTokenClaims, password_hash: str) -> bool:
    return hmac.compare_digest(claims.password_fingerprint, password_fingerprint(password_hash))
