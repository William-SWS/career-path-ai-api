import os

# Settings é carregado na importação de app.main, então o ambiente de teste
# precisa estar definido antes dele. Valores fictícios: nenhum teste deste
# diretório acessa banco, e-mail ou Gemini.
_TEST_ENV = {
    "FRONTEND_HOST": "http://localhost:5173",
    "POSTGRES_DB": "test",
    "POSTGRES_HOST": "localhost",
    "POSTGRES_PORT": "5432",
    "POSTGRES_USER": "test",
    "POSTGRES_PASSWORD": "test",
    "SECRET_KEY": "test-secret-key-with-at-least-32-characters",
    "DEBUG": "false",
    "MAIL_USERNAME": "test",
    "MAIL_PASSWORD": "test",
    "MAIL_FROM": "test@example.com",
    "GEMINI_API_KEY": "test",
}
for key, value in _TEST_ENV.items():
    os.environ.setdefault(key, value)

# Testes de integração (tests/integration) usam um Postgres real indicado por
# TEST_DATABASE_URL, ex.: postgresql://postgres:test@127.0.0.1:55432/test.
# Sem ela, esses testes são pulados e a suíte continua independente de serviços externos.
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
if TEST_DATABASE_URL:
    from sqlalchemy.engine import make_url

    _url = make_url(TEST_DATABASE_URL)
    os.environ.update(
        POSTGRES_HOST=_url.host,
        POSTGRES_PORT=str(_url.port),
        POSTGRES_USER=_url.username,
        POSTGRES_PASSWORD=_url.password,
        POSTGRES_DB=_url.database,
    )

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client() -> TestClient:
    # Sem `with`: cada requisição roda no seu próprio event loop.
    return TestClient(app)


@pytest.fixture(autouse=True)
def fresh_rate_limiter():
    """Contadores zerados a cada teste: o limitador padrão em memória é um singleton do processo."""
    from app.core.rate_limit import get_rate_limiter

    get_rate_limiter.cache_clear()
    yield
    get_rate_limiter.cache_clear()


@pytest.fixture(autouse=True)
def fresh_readiness_cache():
    """O /ready guarda o último resultado por alguns segundos; sem isto um teste herdaria o do anterior."""
    from app.api.v1.routes.health_routes import readiness_cache

    readiness_cache.clear()
    yield
    readiness_cache.clear()
