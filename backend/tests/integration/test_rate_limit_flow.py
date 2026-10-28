"""Rate limit nas rotas reais (HTTP → dependência → serviço → Postgres)."""

import json

import pytest

from app.llm.client import get_llm_client
from app.main import app
from app.schemas.ai_outputs import DevelopmentTrailOutput
from tests.fakes import FakeLLM, sample_output
from tests.integration.conftest import API, CREDENTIALS, bearer

pytestmark = pytest.mark.integration

TRAIL = {"name": "Ana", "skills": ["Python"], "professional_goal": "Back-End"}


def test_login_is_blocked_after_too_many_attempts_for_the_same_account(http):
    http.post(f"{API}/auth/register", json={"name": "Maria", **CREDENTIALS})
    wrong = {"email": CREDENTIALS["email"], "password": "Wrong1234"}

    statuses = [http.post(f"{API}/auth/login", json=wrong).status_code for _ in range(5)]
    blocked = http.post(f"{API}/auth/login", json=CREDENTIALS)  # até a senha certa é barrada

    assert statuses == [401] * 5
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "rate_limit_exceeded"
    assert int(blocked.headers["Retry-After"]) >= 1


def test_blocking_one_account_does_not_block_another_from_the_same_ip(http):
    for _ in range(5):
        http.post(
            f"{API}/auth/login", json={"email": "victim@example.com", "password": "Wrong1234"}
        )

    other = http.post(
        f"{API}/auth/login", json={"email": "other@example.com", "password": "Wrong1234"}
    )

    assert other.status_code == 401  # credencial errada, mas não limitada


def test_registration_is_limited_per_ip(http):
    statuses = [
        http.post(
            f"{API}/auth/register",
            json={"name": "Maria Silva", "email": f"u{i}@example.com", "password": "Abcdef12"},
        ).status_code
        for i in range(4)
    ]

    assert statuses == [201, 201, 201, 429]


def test_ai_generation_is_limited_per_user_and_the_limit_does_not_hide_auth_errors(
    http, session_tokens
):
    app.dependency_overrides[get_llm_client] = lambda: FakeLLM(
        json.dumps(sample_output(DevelopmentTrailOutput))
    )
    headers = bearer(session_tokens["access_token"])

    statuses = [
        http.post(f"{API}/development-trail/", json=TRAIL, headers=headers).status_code
        for _ in range(4)
    ]
    unauthenticated = http.post(f"{API}/development-trail/", json=TRAIL)

    assert statuses == [200, 200, 200, 429]
    assert unauthenticated.status_code == 401  # sem token: 401, nunca consome o limite de ninguém


def test_forgot_password_is_limited_per_email_even_below_the_ip_limit(http, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "RATE_LIMIT_FORGOT_PASSWORD", "10/hour")  # IP não é o gargalo
    body = {"email": "nobody@example.com"}  # conta inexistente: o limite vale igual

    statuses = [http.post(f"{API}/auth/forgot-password", json=body).status_code for _ in range(4)]

    assert statuses == [200, 200, 200, 429]
    assert (
        http.post(f"{API}/auth/forgot-password", json={"email": "other@example.com"}).status_code
        == 200
    )


def test_refresh_and_logout_are_limited(http, session_tokens, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "RATE_LIMIT_REFRESH", "2/minute")
    monkeypatch.setattr(settings, "RATE_LIMIT_LOGOUT", "1/minute")
    refresh = bearer(session_tokens["refresh_token"])
    access = bearer(session_tokens["access_token"])

    refreshed = [http.post(f"{API}/auth/refresh", headers=refresh).status_code for _ in range(3)]
    logouts = [http.post(f"{API}/auth/logout", headers=access).status_code for _ in range(2)]

    assert refreshed == [200, 200, 429]
    assert logouts[0] == 200
    assert logouts == [200, 429]
