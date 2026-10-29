"""Access, refresh e reset são tokens distintos: um nunca vale no lugar do outro."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from jwt import InvalidTokenError

from app.core.config import settings
from app.security.passwords import password_fingerprint
from app.security.tokens import (
    TokenType,
    create_reset_password_token,
    create_token,
    decode_jwt_token,
)
from tests.fakes import unverified_claims

API = "/api/v1"


def sign(claims: dict) -> str:
    return jwt.encode(claims, settings.SECRET_KEY, settings.ALGORITHM)


def expired_token(token_type: TokenType) -> str:
    return create_token(1, "hash", token_type, token_duration=timedelta(seconds=-5))


def test_tokens_carry_their_type():
    claims = lambda t: unverified_claims(t)

    assert claims(create_token(1, "hash"))["type"] == "access"
    assert claims(create_token(1, "hash", TokenType.REFRESH))["type"] == "refresh"
    assert claims(create_reset_password_token("a@b.co", "hash"))["type"] == "reset_password"


def test_refresh_token_outlives_access_token():
    exp = lambda t: unverified_claims(t)["exp"]

    assert exp(create_token(1, "hash", TokenType.REFRESH)) > exp(create_token(1, "hash"))


@pytest.mark.parametrize(
    "token, expected",
    [
        (create_token(1, "hash", TokenType.REFRESH), TokenType.ACCESS),
        (create_token(1, "hash"), TokenType.REFRESH),
        (create_reset_password_token("a@b.co", "hash"), TokenType.ACCESS),
        (create_token(1, "hash"), TokenType.RESET_PASSWORD),
    ],
    ids=["refresh-as-access", "access-as-refresh", "reset-as-access", "access-as-reset"],
)
def test_decode_rejects_a_token_of_another_type(token, expected):
    with pytest.raises(InvalidTokenError):
        decode_jwt_token(token, expected)


def test_decode_rejects_legacy_token_without_type():
    legacy = sign({"sub": "1", "exp": datetime.now(UTC) + timedelta(minutes=5)})

    with pytest.raises(InvalidTokenError):
        decode_jwt_token(legacy, TokenType.ACCESS)


def test_decode_rejects_expired_token():
    with pytest.raises(InvalidTokenError):
        decode_jwt_token(expired_token(TokenType.ACCESS), TokenType.ACCESS)


def test_decode_rejects_token_without_expiration():
    never_expires = sign({"sub": "1", "type": "access"})

    with pytest.raises(InvalidTokenError):
        decode_jwt_token(never_expires, TokenType.ACCESS)


def test_decode_rejects_unsigned_token():
    claims = {"sub": "1", "type": "access", "exp": datetime.now(UTC) + timedelta(minutes=5)}
    unsigned = jwt.encode(claims, None, algorithm="none")

    with pytest.raises(InvalidTokenError):
        decode_jwt_token(unsigned, TokenType.ACCESS)


@pytest.mark.filterwarnings("ignore::jwt.warnings.InsecureKeyLengthWarning")
def test_decode_rejects_token_signed_with_another_algorithm():
    # O algoritmo aceito é só o configurado: HS512 com a mesma chave não vale como HS256.
    other = "HS512" if settings.ALGORITHM != "HS512" else "HS256"
    claims = {"sub": "1", "type": "access", "exp": datetime.now(UTC) + timedelta(minutes=5)}
    token = jwt.encode(claims, settings.SECRET_KEY, algorithm=other)

    with pytest.raises(InvalidTokenError):
        decode_jwt_token(token, TokenType.ACCESS)


def test_decode_rejects_token_signed_with_another_key():
    claims = {"sub": "1", "type": "access", "exp": datetime.now(UTC) + timedelta(minutes=5)}
    forged = jwt.encode(claims, "x" * 64, algorithm=settings.ALGORITHM)

    with pytest.raises(InvalidTokenError):
        decode_jwt_token(forged, TokenType.ACCESS)


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize(
    "token",
    [
        create_token(1, "hash", TokenType.REFRESH),
        create_reset_password_token("a@b.co", "hash"),
        sign({"sub": "1", "exp": datetime.now(UTC) + timedelta(minutes=5)}),
        sign(
            {
                "sub": "not-a-number",
                "type": "access",
                "exp": datetime.now(UTC) + timedelta(minutes=5),
            }
        ),
        sign({"type": "access", "exp": datetime.now(UTC) + timedelta(minutes=5)}),
        expired_token(TokenType.ACCESS),
        "garbage",
    ],
    ids=["refresh", "reset", "legacy-no-type", "non-numeric-sub", "no-sub", "expired", "garbage"],
)
def test_protected_route_rejects_anything_but_a_valid_access_token(client, token):
    response = client.get(f"{API}/users/me", headers=bearer(token))

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "token",
    [
        create_token(1, "hash"),
        expired_token(TokenType.REFRESH),
        create_reset_password_token("a@b.co", "hash"),
        "garbage",
    ],
    ids=["access", "expired-refresh", "reset", "garbage"],
)
def test_refresh_endpoint_rejects_anything_but_a_valid_refresh_token(client, token):
    response = client.post(f"{API}/auth/refresh", headers=bearer(token))

    assert response.status_code == 401


def test_refresh_endpoint_requires_a_token(client):
    assert client.post(f"{API}/auth/refresh").status_code == 401


def test_every_token_is_unique_even_when_issued_in_the_same_second():
    # Sem jti, dois logins no mesmo segundo gerariam a mesma string, e revogar
    # um token (a blacklist guarda o jti) revogaria o outro.
    assert create_token(1, "hash") != create_token(1, "hash")
    assert create_token(1, "hash", TokenType.REFRESH) != create_token(1, "hash", TokenType.REFRESH)


def test_session_tokens_carry_the_password_fingerprint_and_not_the_hash():
    for token_type in (TokenType.ACCESS, TokenType.REFRESH):
        payload = unverified_claims(create_token(1, "hash-a", token_type))

        assert payload["pwd"] == password_fingerprint("hash-a")
        assert "hash-a" not in payload["pwd"]


def test_fingerprint_changes_with_the_password():
    assert password_fingerprint("hash-a") != password_fingerprint("hash-b")
