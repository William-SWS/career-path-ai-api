import asyncio
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from jwt import InvalidTokenError

from app.core.config import settings
from app.security.blacklist import is_token_blacklisted, revoke_token_once
from app.security.tokens import (
    TokenType,
    create_reset_password_token,
    create_token,
    decode_jwt_payload,
    decode_jwt_token,
)


def test_decode_returns_payload_for_valid_token():
    assert decode_jwt_token(create_token(42, "hash"), TokenType.ACCESS)["sub"] == "42"


def test_decode_raises_jwt_error_not_http_exception_for_invalid_token():
    with pytest.raises(InvalidTokenError):
        decode_jwt_token("garbage", TokenType.ACCESS)


def test_payload_decode_accepts_any_token_type():
    tokens = {
        TokenType.ACCESS: create_token(1, "hash"),
        TokenType.REFRESH: create_token(1, "hash", TokenType.REFRESH),
        TokenType.RESET_PASSWORD: create_reset_password_token("a@example.com", "hash"),
    }

    assert {decode_jwt_payload(token)["type"] for token in tokens.values()} == {
        token_type.value for token_type in TokenType
    }


def sign(claims: dict, key: str = settings.SECRET_KEY, algorithm: str = settings.ALGORITHM) -> str:
    return jwt.encode(claims, key, algorithm)


def valid_claims(**overrides) -> dict:
    claims = {
        "sub": "1",
        "type": "access",
        "jti": "a" * 32,
        "exp": datetime.now(UTC) + timedelta(minutes=5),
    }
    return {key: value for key, value in {**claims, **overrides}.items() if value is not None}


# Tokens que nenhuma parte do sistema pode aceitar. O decode por tipo e a blacklist usam a mesma
# configuração (`decode_jwt_payload`), então a revogação não pode ser mais frouxa que a validação.
REJECTED = {
    "garbage": "garbage",
    "expired": sign(valid_claims(exp=datetime.now(UTC) - timedelta(seconds=5))),
    "without-exp": sign(valid_claims(exp=None)),
    "without-sub": sign(valid_claims(sub=None)),
    "another-key": sign(valid_claims(), key="x" * 64),
    "unsigned": jwt.encode(valid_claims(), None, algorithm="none"),
}


@pytest.mark.parametrize("token", REJECTED.values(), ids=REJECTED.keys())
def test_payload_decode_rejects_what_the_typed_decode_rejects(token):
    with pytest.raises(InvalidTokenError):
        decode_jwt_payload(token)
    with pytest.raises(InvalidTokenError):
        decode_jwt_token(token, TokenType.ACCESS)


@pytest.mark.parametrize("token", REJECTED.values(), ids=REJECTED.keys())
def test_blacklist_ignores_the_same_tokens(token):
    # Retornam antes de tocar o banco, por isso `db=None`.
    assert asyncio.run(revoke_token_once(token, None)) is None  # type: ignore[arg-type]
    assert asyncio.run(is_token_blacklisted(token, None)) is False  # type: ignore[arg-type]
