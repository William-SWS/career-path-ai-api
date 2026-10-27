import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import BackgroundTasks

from app.core.exceptions import (
    AuthenticationException,
    ConflictException,
    NotFoundException,
    PermissionDeniedException,
    ValidationException,
)
from app.core.security import bcrypt_context
from app.schemas.auth_schema import (
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
)
from app.schemas.user_schema import UserDeleteRequest, UserUpdateRequest
from app.services.user_services import UserService
from app.core.security import TokenType, create_token
from app.services import user_services
from app.utils.token_utils import create_reset_password_token
from tests.fakes import FakeSession

PASSWORD = "Abcdef12"
PASSWORD_HASH = bcrypt_context.hash(PASSWORD)  # bcrypt é lento: calcula uma vez


class FakeUserRepository:
    """Repositório em memória: isola as regras do UserService do banco."""

    def __init__(self, users=()):
        self.users = {user.email: user for user in users}
        self.deleted_ids = []

    async def get_by_email(self, email):
        return self.users.get(email)

    async def email_exists(self, email):
        return email in self.users

    async def get_by_id(self, user_id):
        return next((u for u in self.users.values() if u.id == user_id), None)

    async def create(self, **fields):
        user = SimpleNamespace(id=len(self.users) + 1, **fields)
        self.users[user.email] = user
        return user

    async def update(self, user_id, **fields):
        user = await self.get_by_id(user_id)
        for key, value in fields.items():
            setattr(user, key, value)
        return user

    async def delete(self, user_id):
        self.deleted_ids.append(user_id)

    async def update_password(self, user_id, hashed_password):
        user = await self.get_by_id(user_id)
        user.password_hash = hashed_password
        return user


def make_user(id=1, email="maria@example.com"):
    return SimpleNamespace(
        id=id,
        email=email,
        name="Maria Silva",
        password_hash=PASSWORD_HASH,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def make_service(*users, session=None):
    service = UserService(db=session or FakeSession())
    service.user_repository = FakeUserRepository(users)
    return service


def run(coro):
    return asyncio.run(coro)


def test_register_with_existing_email_is_conflict():
    service = make_service(make_user())
    data = RegisterRequest(name="Outra Pessoa", email="maria@example.com", password=PASSWORD)

    with pytest.raises(ConflictException) as exc_info:
        run(service.create_user_account(data))

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "email_already_registered"


def test_register_stores_hashed_password():
    service = make_service()
    data = RegisterRequest(name="Maria Silva", email="maria@example.com", password=PASSWORD)

    run(service.create_user_account(data))

    stored = service.user_repository.users["maria@example.com"]
    assert stored.password_hash != PASSWORD
    assert bcrypt_context.verify(PASSWORD, stored.password_hash)


@pytest.mark.parametrize(
    "email, password",
    [("maria@example.com", "WrongPass1"), ("ghost@example.com", PASSWORD)],
)
def test_login_with_bad_credentials_is_unauthorized(email, password):
    service = make_service(make_user())

    with pytest.raises(AuthenticationException) as exc_info:
        run(service.login(LoginRequest(email=email, password=password)))

    assert exc_info.value.status_code == 401
    assert exc_info.value.code == "invalid_credentials"


def test_login_returns_both_tokens():
    service = make_service(make_user())

    response = run(service.login(LoginRequest(email="maria@example.com", password=PASSWORD)))

    assert response.tokens.access_token
    assert response.tokens.refresh_token
    assert response.data.email == "maria@example.com"


def test_update_without_fields_is_validation_error():
    service = make_service(make_user())

    with pytest.raises(ValidationException) as exc_info:
        run(service.update_user(UserUpdateRequest(), make_user()))

    assert exc_info.value.code == "no_fields_to_update"


def test_update_to_email_used_by_someone_else_is_conflict():
    me, other = make_user(1, "me@example.com"), make_user(2, "other@example.com")
    service = make_service(me, other)

    with pytest.raises(ConflictException):
        run(service.update_user(UserUpdateRequest(email="other@example.com"), me))


def test_update_keeping_own_email_is_allowed():
    me = make_user(1, "me@example.com")
    service = make_service(me)

    result = run(service.update_user(UserUpdateRequest(email="me@example.com", name="Maria Souza"), me))

    assert result.name == "Maria Souza"


def test_delete_with_wrong_password_is_forbidden_not_unauthorized():
    me = make_user()
    service = make_service(me)

    with pytest.raises(PermissionDeniedException) as exc_info:
        run(service.delete_user(UserDeleteRequest(password="WrongPass1"), me))

    assert exc_info.value.status_code == 403
    assert service.user_repository.deleted_ids == []


def test_delete_with_correct_password_removes_user():
    me = make_user()
    service = make_service(me)

    run(service.delete_user(UserDeleteRequest(password=PASSWORD), me))

    assert service.user_repository.deleted_ids == [me.id]


def test_forgot_password_for_unknown_email_is_validation_error():
    service = make_service()

    with pytest.raises(ValidationException):
        run(service.forgot_user_password(ForgotPasswordRequest(email="x@example.com"), BackgroundTasks()))


def test_reset_password_with_invalid_token_is_validation_error():
    service = make_service(make_user())
    data = ResetPasswordRequest(reset_token="not-a-jwt", new_password="Newpass12")

    with pytest.raises(ValidationException) as exc_info:
        run(service.reset_user_password(data))

    assert exc_info.value.code == "invalid_reset_token"


def test_reset_password_for_deleted_user_is_not_found():
    service = make_service()
    token = create_reset_password_token("ghost@example.com")

    with pytest.raises(NotFoundException):
        run(service.reset_user_password(ResetPasswordRequest(reset_token=token, new_password="Newpass12")))


# ---------- fronteira transacional: um commit por escrita, nenhum por leitura ou falha

def test_successful_writes_commit_exactly_once():
    me = make_user()
    reset_token = create_reset_password_token(me.email)
    calls = {
        "register": lambda s: s.create_user_account(
            RegisterRequest(name="Ana Souza", email="ana@example.com", password=PASSWORD)),
        "update": lambda s: s.update_user(UserUpdateRequest(name="Maria Souza"), me),
        "delete": lambda s: s.delete_user(UserDeleteRequest(password=PASSWORD), me),
        "reset": lambda s: s.reset_user_password(
            ResetPasswordRequest(reset_token=reset_token, new_password="Newpass12")),
        "logout": lambda s: s.logout(create_token(me.id), me),
    }

    for name, call in calls.items():
        service = make_service(me)
        run(call(service))
        assert service.db.commits == 1, name


def test_reads_and_failed_writes_never_commit():
    me = make_user()
    attempts = [
        (ConflictException, lambda s: s.create_user_account(
            RegisterRequest(name="Ana Souza", email=me.email, password=PASSWORD))),
        (ValidationException, lambda s: s.update_user(UserUpdateRequest(), me)),
        (PermissionDeniedException, lambda s: s.delete_user(UserDeleteRequest(password="WrongPass1"), me)),
        (ValidationException, lambda s: s.reset_user_password(
            ResetPasswordRequest(reset_token="bad", new_password="Newpass12"))),
        (AuthenticationException, lambda s: s.login(LoginRequest(email=me.email, password="WrongPass1"))),
    ]

    for expected, call in attempts:
        service = make_service(me)
        with pytest.raises(expected):
            run(call(service))
        assert service.db.commits == 0

    service = make_service(me)
    run(service.login(LoginRequest(email=me.email, password=PASSWORD)))
    run(service.retrieve_user_data(me))
    assert service.db.commits == 0


def test_logout_blacklists_the_token_it_received():
    service = make_service(make_user())
    token = create_token(1)

    run(service.logout(token, make_user()))

    assert [entry.token for entry in service.db.added] == [token]


def test_logout_does_not_report_success_when_the_blacklist_write_fails():
    service = make_service(make_user(), session=FakeSession(commit_error=RuntimeError("db down")))

    with pytest.raises(RuntimeError):
        run(service.logout(create_token(1), make_user()))


# ---------- logout revoga access e refresh token na mesma transação

def stub_blacklist(monkeypatch, already_revoked=()):
    async def is_blacklisted(token, db):
        return token in already_revoked

    monkeypatch.setattr(user_services, "is_token_blacklisted", is_blacklisted)


def revoked(service):
    return [entry.token for entry in service.db.added]


def test_logout_revokes_access_and_refresh_token_in_one_commit(monkeypatch):
    stub_blacklist(monkeypatch)
    me = make_user()
    access, refresh = create_token(me.id), create_token(me.id, TokenType.REFRESH)
    service = make_service(me)

    run(service.logout(access, me, refresh))

    assert revoked(service) == [access, refresh]
    assert service.db.commits == 1


def test_logout_without_refresh_token_revokes_only_the_access_token(monkeypatch):
    stub_blacklist(monkeypatch)
    me = make_user()
    access = create_token(me.id)
    service = make_service(me)

    run(service.logout(access, me))

    assert revoked(service) == [access]


@pytest.mark.parametrize(
    "unusable",
    [
        create_token(1, TokenType.REFRESH, token_duration=timedelta(seconds=-5)),
        create_token(1),  # access token enviado no lugar do refresh
        "garbage",
    ],
    ids=["expired", "wrong-type", "garbage"],
)
def test_logout_succeeds_when_the_refresh_token_has_nothing_to_revoke(monkeypatch, unusable):
    stub_blacklist(monkeypatch)
    me = make_user()
    access = create_token(me.id)
    service = make_service(me)

    run(service.logout(access, me, unusable))

    assert revoked(service) == [access]
    assert service.db.commits == 1


def test_logout_is_idempotent_for_an_already_revoked_refresh_token(monkeypatch):
    me = make_user()
    access, refresh = create_token(me.id), create_token(me.id, TokenType.REFRESH)
    stub_blacklist(monkeypatch, already_revoked={refresh})
    service = make_service(me)

    run(service.logout(access, me, refresh))

    assert revoked(service) == [access]


def test_logout_rejects_a_refresh_token_of_another_user_and_revokes_nothing(monkeypatch):
    stub_blacklist(monkeypatch)
    me = make_user(id=1)
    someone_elses = create_token(2, TokenType.REFRESH)
    service = make_service(me)

    with pytest.raises(ValidationException) as exc_info:
        run(service.logout(create_token(1), me, someone_elses))

    assert exc_info.value.code == "refresh_token_mismatch"
    assert revoked(service) == []
    assert service.db.commits == 0
