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
