"""Fluxo de autenticação ponta a ponta (HTTP → serviço → Postgres real)."""
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.database import get_db
from app.core.security import TokenType, create_token
from app.main import app

pytestmark = pytest.mark.integration

API = "/api/v1"
CREDENTIALS = {"email": "maria@example.com", "password": "Abcdef12"}


@pytest.fixture
def http():
    # Uma sessão por requisição, sem pool: o TestClient roda em outro event loop.
    engine = create_async_engine(settings.DATABASE_URI, poolclass=NullPool)
    maker = async_sessionmaker(engine, class_=AsyncSession, autoflush=False)

    async def session_per_request():
        async with maker() as session:
            yield session

    app.dependency_overrides[get_db] = session_per_request
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def session_tokens(http):
    http.post(f"{API}/auth/register", json={"name": "Maria Silva", **CREDENTIALS})
    return http.post(f"{API}/auth/login", json=CREDENTIALS).json()["tokens"]


def test_login_issues_a_working_access_token(http, session_tokens):
    response = http.get(f"{API}/users/me", headers=bearer(session_tokens["access_token"]))

    assert response.status_code == 200
    assert response.json()["email"] == CREDENTIALS["email"]


def test_refresh_token_cannot_be_used_as_access_token(http, session_tokens):
    response = http.get(f"{API}/users/me", headers=bearer(session_tokens["refresh_token"]))

    assert response.status_code == 401


def test_refresh_issues_a_new_working_access_token(http, session_tokens):
    refreshed = http.post(f"{API}/auth/refresh", headers=bearer(session_tokens["refresh_token"]))

    assert refreshed.status_code == 200
    new_access = refreshed.json()["access_token"]
    assert http.get(f"{API}/users/me", headers=bearer(new_access)).status_code == 200


def test_access_token_cannot_renew_the_session(http, session_tokens):
    response = http.post(f"{API}/auth/refresh", headers=bearer(session_tokens["access_token"]))

    assert response.status_code == 401


def test_expired_refresh_token_cannot_renew_the_session(http, session_tokens):
    expired = create_token(1, TokenType.REFRESH, token_duration=timedelta(seconds=-5))

    assert http.post(f"{API}/auth/refresh", headers=bearer(expired)).status_code == 401


def test_logged_out_access_token_is_rejected(http, session_tokens):
    access = session_tokens["access_token"]

    assert http.post(f"{API}/auth/logout", headers=bearer(access)).status_code == 200
    assert http.get(f"{API}/users/me", headers=bearer(access)).status_code == 401


def test_token_of_a_deleted_user_is_rejected(http, session_tokens):
    access = session_tokens["access_token"]
    deleted = http.request(
        "DELETE", f"{API}/users/me/delete", headers=bearer(access), json={"password": CREDENTIALS["password"]}
    )

    assert deleted.status_code == 200
    assert http.get(f"{API}/users/me", headers=bearer(access)).status_code == 401


def logout(http, tokens, **body):
    return http.post(f"{API}/auth/logout", headers=bearer(tokens["access_token"]), json=body or None)


def test_logout_with_refresh_token_ends_the_whole_session(http, session_tokens):
    assert logout(http, session_tokens, refresh_token=session_tokens["refresh_token"]).status_code == 200

    renewed = http.post(f"{API}/auth/refresh", headers=bearer(session_tokens["refresh_token"]))
    assert renewed.status_code == 401


def test_logout_without_refresh_token_still_works_for_old_clients(http, session_tokens):
    assert logout(http, session_tokens).status_code == 200


def test_revoking_the_same_refresh_token_twice_is_not_an_error(http, session_tokens):
    refresh = session_tokens["refresh_token"]
    assert logout(http, session_tokens, refresh_token=refresh).status_code == 200

    second_login = http.post(f"{API}/auth/login", json=CREDENTIALS).json()["tokens"]
    assert logout(http, second_login, refresh_token=refresh).status_code == 200


def test_logout_rejects_a_refresh_token_of_another_user(http, session_tokens):
    http.post(f"{API}/auth/register", json={"name": "Ana Souza", "email": "ana@example.com", "password": "Abcdef12"})
    other = http.post(f"{API}/auth/login", json={"email": "ana@example.com", "password": "Abcdef12"}).json()["tokens"]

    response = logout(http, session_tokens, refresh_token=other["refresh_token"])

    assert response.status_code == 400
    # nada foi revogado: o access token ainda vale e a sessão da Ana segue renovável
    assert http.get(f"{API}/users/me", headers=bearer(session_tokens["access_token"])).status_code == 200
    assert http.post(f"{API}/auth/refresh", headers=bearer(other["refresh_token"])).status_code == 200
