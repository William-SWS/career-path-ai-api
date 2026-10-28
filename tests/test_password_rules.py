import pytest
from pydantic import ValidationError

from app.schemas.auth_schema import LoginRequest, RegisterRequest, ResetPasswordRequest

API = "/api/v1"


def register(password):
    return RegisterRequest(name="Maria Silva", email="maria@example.com", password=password)


def reset(password):
    return ResetPasswordRequest(reset_token="token", new_password=password)


def password_of(size_in_bytes: int, char: str = "a") -> str:
    """Senha válida (maiúscula, minúscula, número) com exatamente `size_in_bytes` bytes."""
    body = "Aa1" + char * ((size_in_bytes - 3) // len(char.encode()))
    assert len(body.encode()) == size_in_bytes
    return body


@pytest.mark.parametrize("build", [register, reset], ids=["register", "reset"])
def test_accepts_a_password_of_exactly_72_bytes(build):
    assert build(password_of(72))


@pytest.mark.parametrize("build", [register, reset], ids=["register", "reset"])
def test_rejects_more_than_72_bytes_because_bcrypt_would_truncate_silently(build):
    with pytest.raises(ValidationError) as exc_info:
        build(password_of(73))

    assert "72" in str(exc_info.value)


@pytest.mark.parametrize("build", [register, reset], ids=["register", "reset"])
def test_counts_bytes_not_characters(build):
    # "ã" ocupa 2 bytes em UTF-8: poucos caracteres já passam de 72 bytes.
    long_in_bytes = password_of(79, char="ã")
    assert len(long_in_bytes) < 72

    with pytest.raises(ValidationError):
        build(long_in_bytes)


def test_login_still_accepts_long_passwords_so_existing_users_are_not_locked_out():
    assert LoginRequest(email="maria@example.com", password="Aa1" + "a" * 90)


def test_the_api_reports_the_limit_per_field(client):
    response = client.post(
        f"{API}/auth/register",
        json={"email": "maria@example.com", "name": "Maria Silva", "password": password_of(73)},
    )

    assert response.status_code == 422
    [detail] = response.json()["error"]["details"]
    assert detail["field"] == "password"
