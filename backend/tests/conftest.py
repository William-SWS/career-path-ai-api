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
    "SECRET_KEY": "test-secret-key",
    "DEBUG": "false",
    "MAIL_USERNAME": "test",
    "MAIL_PASSWORD": "test",
    "MAIL_FROM": "test@example.com",
    "GEMINI_API_KEY": "test",
}
for key, value in _TEST_ENV.items():
    os.environ.setdefault(key, value)

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client() -> TestClient:
    # Sem `with`: o lifespan (scheduler de limpeza de tokens) não é executado.
    return TestClient(app)
