import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.exception_handlers import register_exception_handlers
from app.core.exceptions import ConflictException

SECRET = "postgres://user:s3cr3t@db/internal"


@pytest.fixture(scope="module")
def isolated_client():
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/conflict")
    async def conflict():
        raise ConflictException("Já existe", code="already_exists")

    @app.get("/boom")
    async def boom():
        raise RuntimeError(SECRET)

    # raise_server_exceptions=False: devolve a resposta do handler 500 em vez de relançar.
    return TestClient(app, raise_server_exceptions=False)


def test_app_exception_is_translated_to_http_error(isolated_client):
    response = isolated_client.get("/conflict")

    assert response.status_code == 409
    assert response.json() == {
        "error": {"status": 409, "code": "already_exists", "message": "Já existe"}
    }


def test_unexpected_exception_returns_generic_500_without_details(isolated_client):
    response = isolated_client.get("/boom")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_server_error"
    assert SECRET not in response.text


def test_weak_password_is_reported_per_field(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "maria@example.com", "name": "Maria Silva", "password": "abcdefgh"},
    )

    assert response.status_code == 422
    details = response.json()["error"]["details"]
    assert details == [
        {
            "field": "password",
            "message": "A senha deve conter uma letra maiúscula, um número.",
        }
    ]


def test_invalid_name_is_reported_per_field_without_echoing_input(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "maria@example.com", "name": "Maria", "password": "Abcdef12"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["details"] == [
        {"field": "name", "message": "Informe nome e sobrenome."}
    ]
