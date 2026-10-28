"""Fluxo de autenticação ponta a ponta (HTTP → serviço → Postgres real)."""

from datetime import UTC, datetime, timedelta

import pytest
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.security import TokenType, create_token
from tests.integration.conftest import API, CREDENTIALS, bearer

pytestmark = pytest.mark.integration


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
    expired = create_token(1, "hash", TokenType.REFRESH, token_duration=timedelta(seconds=-5))

    assert http.post(f"{API}/auth/refresh", headers=bearer(expired)).status_code == 401


def test_logged_out_access_token_is_rejected(http, session_tokens):
    access = session_tokens["access_token"]

    assert http.post(f"{API}/auth/logout", headers=bearer(access)).status_code == 200
    assert http.get(f"{API}/users/me", headers=bearer(access)).status_code == 401


def test_token_of_a_deleted_user_is_rejected(http, session_tokens):
    access = session_tokens["access_token"]
    deleted = http.request(
        "DELETE",
        f"{API}/users/me/delete",
        headers=bearer(access),
        json={"password": CREDENTIALS["password"]},
    )

    assert deleted.status_code == 200
    assert http.get(f"{API}/users/me", headers=bearer(access)).status_code == 401


def logout(http, tokens, **body):
    return http.post(
        f"{API}/auth/logout", headers=bearer(tokens["access_token"]), json=body or None
    )


def test_logout_with_refresh_token_ends_the_whole_session(http, session_tokens):
    assert (
        logout(http, session_tokens, refresh_token=session_tokens["refresh_token"]).status_code
        == 200
    )

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
    http.post(
        f"{API}/auth/register",
        json={"name": "Ana Souza", "email": "ana@example.com", "password": "Abcdef12"},
    )
    other = http.post(
        f"{API}/auth/login", json={"email": "ana@example.com", "password": "Abcdef12"}
    ).json()["tokens"]

    response = logout(http, session_tokens, refresh_token=other["refresh_token"])

    assert response.status_code == 400
    # nada foi revogado: o access token ainda vale e a sessão da Ana segue renovável
    assert (
        http.get(f"{API}/users/me", headers=bearer(session_tokens["access_token"])).status_code
        == 200
    )
    assert (
        http.post(f"{API}/auth/refresh", headers=bearer(other["refresh_token"])).status_code == 200
    )


def reset_token_for(http, email):
    """Token como o enviado por e-mail, montado a partir do hash gravado no banco."""
    import asyncio

    from app.repository.user_repository import UserRepository

    async def stored_hash():
        engine = create_async_engine(settings.DATABASE_URI, poolclass=NullPool)
        try:
            async with async_sessionmaker(engine, class_=AsyncSession)() as session:
                return (await UserRepository(session).get_by_email(email)).password_hash
        finally:
            await engine.dispose()

    from app.utils.token_utils import create_reset_password_token

    return create_reset_password_token(email, asyncio.run(stored_hash()))


def test_password_reset_works_once_and_changes_the_credentials(http, session_tokens):
    token = reset_token_for(http, CREDENTIALS["email"])
    reset = lambda password: http.post(
        f"{API}/auth/reset-password", json={"reset_token": token, "new_password": password}
    )

    assert reset("Newpass12").status_code == 200
    assert reset("Another123").status_code == 400  # mesmo token, segunda vez

    login = lambda password: http.post(
        f"{API}/auth/login", json={"email": CREDENTIALS["email"], "password": password}
    )
    assert login("Newpass12").status_code == 200
    assert login(CREDENTIALS["password"]).status_code == 401
    assert login("Another123").status_code == 401


def test_password_reset_ends_every_session_issued_before_it(http, session_tokens):
    old_access, old_refresh = session_tokens["access_token"], session_tokens["refresh_token"]
    assert http.get(f"{API}/users/me", headers=bearer(old_access)).status_code == 200

    token = reset_token_for(http, CREDENTIALS["email"])
    reset = http.post(
        f"{API}/auth/reset-password", json={"reset_token": token, "new_password": "Newpass12"}
    )
    assert reset.status_code == 200

    assert http.get(f"{API}/users/me", headers=bearer(old_access)).status_code == 401
    assert http.post(f"{API}/auth/refresh", headers=bearer(old_refresh)).status_code == 401

    # Quem entra de novo com a senha nova tem uma sessão que funciona.
    login = http.post(
        f"{API}/auth/login", json={"email": CREDENTIALS["email"], "password": "Newpass12"}
    )
    new_access = login.json()["tokens"]["access_token"]
    assert http.get(f"{API}/users/me", headers=bearer(new_access)).status_code == 200


def test_token_without_the_password_claim_is_rejected(http, session_tokens):
    """Token emitido antes desta claim existir (ou forjado sem ela) não vale."""
    claims = {
        "sub": "1",
        "type": "access",
        "exp": datetime.now(UTC) + timedelta(minutes=5),
    }
    legacy = jwt.encode(claims, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    assert http.get(f"{API}/users/me", headers=bearer(legacy)).status_code == 401


@pytest.fixture
def outbox(monkeypatch):
    """Intercepta o FastMail: nenhum e-mail real é enviado."""
    sent = []

    class FakeMail:
        def __init__(self, config):
            pass

        async def send_message(self, message, template_name=None):
            sent.append(message)

    monkeypatch.setattr("app.core.email.FastMail", FakeMail)
    return sent


def test_forgot_password_response_does_not_reveal_which_accounts_exist(
    http, session_tokens, outbox
):
    ask = lambda email: http.post(f"{API}/auth/forgot-password", json={"email": email})

    known, unknown = ask(CREDENTIALS["email"]), ask("ghost@example.com")

    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()
    assert [m.recipients[0].email for m in outbox] == [CREDENTIALS["email"]]


def test_the_emailed_link_resets_the_password(http, session_tokens, outbox):
    http.post(f"{API}/auth/forgot-password", json={"email": CREDENTIALS["email"]})

    link = outbox[0].template_body["reset_url"]
    token = link.split("token=")[1]
    reset = http.post(
        f"{API}/auth/reset-password", json={"reset_token": token, "new_password": "Newpass12"}
    )

    assert reset.status_code == 200


def test_login_error_is_the_same_for_unknown_account_and_wrong_password(http, session_tokens):
    wrong_password = http.post(f"{API}/auth/login", json={**CREDENTIALS, "password": "WrongPass1"})
    unknown_account = http.post(
        f"{API}/auth/login", json={"email": "ghost@example.com", "password": "WrongPass1"}
    )

    assert wrong_password.status_code == unknown_account.status_code == 401
    assert wrong_password.json() == unknown_account.json()
