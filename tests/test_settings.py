import pytest
from pydantic import ValidationError

from app.core.config import Settings

STRONG_KEY = "k" * 32


def build(**overrides):
    # O restante dos campos vem do ambiente definido em conftest.py.
    return Settings(_env_file=None, **overrides)


def test_accepts_a_strong_secret_key():
    assert build(SECRET_KEY=STRONG_KEY).SECRET_KEY == STRONG_KEY


@pytest.mark.parametrize("weak", ["", "short", "k" * 31])
def test_rejects_a_weak_secret_key(weak):
    with pytest.raises(ValidationError) as exc_info:
        build(SECRET_KEY=weak)

    assert "SECRET_KEY" in str(exc_info.value)
    assert weak not in str(exc_info.value) or weak == ""  # nunca ecoa a chave


def test_error_tells_how_to_generate_a_key():
    with pytest.raises(ValidationError) as exc_info:
        build(SECRET_KEY="short")

    assert "secrets.token_urlsafe" in str(exc_info.value)


@pytest.mark.parametrize("algorithm", ["none", "RS256", "hs256 "])
def test_rejects_non_hmac_signing_algorithms(algorithm):
    with pytest.raises(ValidationError):
        build(SECRET_KEY=STRONG_KEY, ALGORITHM=algorithm)


@pytest.mark.parametrize("algorithm", ["HS256", "HS384", "HS512"])
def test_accepts_hmac_signing_algorithms(algorithm):
    assert build(SECRET_KEY=STRONG_KEY, ALGORITHM=algorithm).ALGORITHM == algorithm


@pytest.mark.parametrize("origin", ["http://localhost:5173", "https://app.example.com"])
def test_accepts_a_frontend_origin(origin):
    assert build(FRONTEND_HOST=origin).FRONTEND_HOST == origin


def test_frontend_host_drops_the_trailing_slash():
    # Evita "//reset" no link do e-mail e uma origem que o CORS nunca reconheceria.
    assert (
        build(FRONTEND_HOST="https://app.example.com/").FRONTEND_HOST == "https://app.example.com"
    )


@pytest.mark.parametrize(
    "not_an_origin",
    [
        "",
        "localhost:5173",  # sem esquema: o CORS nunca bateria
        "//localhost:5173",
        "ftp://localhost:5173",
        "http://",
        "http://localhost:5173/app",  # caminho não faz parte da origem
        "http://localhost:5173?x=1",
        " http://localhost:5173",
    ],
)
def test_rejects_a_frontend_host_that_is_not_an_origin(not_an_origin):
    with pytest.raises(ValidationError) as exc_info:
        build(FRONTEND_HOST=not_an_origin)

    assert "FRONTEND_HOST" in str(exc_info.value)
    assert "http://localhost:5173" in str(exc_info.value)  # a mensagem mostra o formato certo
