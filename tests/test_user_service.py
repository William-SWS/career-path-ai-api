import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import jwt
import pytest
from fastapi import BackgroundTasks

from app.core.config import settings
from app.core.exceptions import (
    AuthenticationException,
    ConflictException,
    NotFoundException,
    PermissionDeniedException,
    ValidationException,
)
from app.schemas.auth_schema import (
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
)
from app.schemas.user_schema import UserDeleteRequest, UserUpdateRequest
from app.security.passwords import bcrypt_context
from app.security.tokens import TokenType, create_reset_password_token, create_token
from app.services import user_service
from app.services.user_service import UserService
from tests.fakes import FakeSession, unverified_claims

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
        if user is None:  # como o repositório real
            return None
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
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
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

    result = run(
        service.update_user(UserUpdateRequest(email="me@example.com", name="Maria Souza"), me)
    )

    assert result.name == "Maria Souza"


def test_update_when_the_user_vanished_is_not_found_and_nothing_is_committed():
    me = make_user(1, "me@example.com")
    service = make_service()  # o usuário autenticado já não existe no repositório

    with pytest.raises(NotFoundException) as exc_info:
        run(service.update_user(UserUpdateRequest(name="Maria Souza"), me))

    assert exc_info.value.code == "user_not_found"
    assert service.db.commits == 0


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


def test_reset_password_with_invalid_token_is_validation_error():
    service = make_service(make_user())
    data = ResetPasswordRequest(reset_token="not-a-jwt", new_password="Newpass12")

    with pytest.raises(ValidationException) as exc_info:
        run(service.reset_user_password(data))

    assert exc_info.value.code == "invalid_reset_token"


def test_reset_password_for_deleted_user_is_not_found():
    service = make_service()
    token = create_reset_password_token("ghost@example.com", "hash")

    with pytest.raises(NotFoundException):
        run(
            service.reset_user_password(
                ResetPasswordRequest(reset_token=token, new_password="Newpass12")
            )
        )


# ---------- fronteira transacional: um commit por escrita, nenhum por leitura ou falha


def test_successful_writes_commit_exactly_once():
    me = make_user()
    reset_token = create_reset_password_token(me.email, me.password_hash)
    calls = {
        "register": lambda s: s.create_user_account(
            RegisterRequest(name="Ana Souza", email="ana@example.com", password=PASSWORD)
        ),
        "update": lambda s: s.update_user(UserUpdateRequest(name="Maria Souza"), me),
        "delete": lambda s: s.delete_user(UserDeleteRequest(password=PASSWORD), me),
        "reset": lambda s: s.reset_user_password(
            ResetPasswordRequest(reset_token=reset_token, new_password="Newpass12")
        ),
        "logout": lambda s: s.logout(create_token(me.id, "hash"), me),
    }

    for name, call in calls.items():
        service = make_service(me)
        run(call(service))
        assert service.db.commits == 1, name


def test_reads_and_failed_writes_never_commit():
    me = make_user()
    attempts = [
        (
            ConflictException,
            lambda s: s.create_user_account(
                RegisterRequest(name="Ana Souza", email=me.email, password=PASSWORD)
            ),
        ),
        (ValidationException, lambda s: s.update_user(UserUpdateRequest(), me)),
        (
            PermissionDeniedException,
            lambda s: s.delete_user(UserDeleteRequest(password="WrongPass1"), me),
        ),
        (
            ValidationException,
            lambda s: s.reset_user_password(
                ResetPasswordRequest(reset_token="bad", new_password="Newpass12")
            ),
        ),
        (
            AuthenticationException,
            lambda s: s.login(LoginRequest(email=me.email, password="WrongPass1")),
        ),
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
    token = create_token(1, "hash")

    run(service.logout(token, make_user()))

    assert revoked(service) == [jti(token)]


def test_logout_does_not_report_success_when_the_blacklist_write_fails():
    service = make_service(make_user(), session=FakeSession(commit_error=RuntimeError("db down")))

    with pytest.raises(RuntimeError):
        run(service.logout(create_token(1, "hash"), make_user()))


# ---------- logout revoga access e refresh token na mesma transação


def stub_blacklist(monkeypatch, already_revoked=()):
    async def is_blacklisted(token, db):
        return token in already_revoked

    monkeypatch.setattr(user_service, "is_token_blacklisted", is_blacklisted)


def revoked(service):
    return [entry.jti for entry in service.db.added]


def jti(token):
    return unverified_claims(token)["jti"]


def test_logout_revokes_access_and_refresh_token_in_one_commit(monkeypatch):
    stub_blacklist(monkeypatch)
    me = make_user()
    access, refresh = create_token(me.id, "hash"), create_token(me.id, "hash", TokenType.REFRESH)
    service = make_service(me)

    run(service.logout(access, me, refresh))

    assert revoked(service) == [jti(access), jti(refresh)]
    assert service.db.commits == 1


def test_logout_without_refresh_token_revokes_only_the_access_token(monkeypatch):
    stub_blacklist(monkeypatch)
    me = make_user()
    access = create_token(me.id, "hash")
    service = make_service(me)

    run(service.logout(access, me))

    assert revoked(service) == [jti(access)]


@pytest.mark.parametrize(
    "unusable",
    [
        create_token(1, "hash", TokenType.REFRESH, token_duration=timedelta(seconds=-5)),
        create_token(1, "hash"),  # access token enviado no lugar do refresh
        "garbage",
    ],
    ids=["expired", "wrong-type", "garbage"],
)
def test_logout_succeeds_when_the_refresh_token_has_nothing_to_revoke(monkeypatch, unusable):
    stub_blacklist(monkeypatch)
    me = make_user()
    access = create_token(me.id, "hash")
    service = make_service(me)

    run(service.logout(access, me, unusable))

    assert revoked(service) == [jti(access)]
    assert service.db.commits == 1


def test_logout_is_idempotent_for_an_already_revoked_refresh_token(monkeypatch):
    me = make_user()
    access, refresh = create_token(me.id, "hash"), create_token(me.id, "hash", TokenType.REFRESH)
    stub_blacklist(monkeypatch, already_revoked={refresh})
    service = make_service(me)

    run(service.logout(access, me, refresh))

    assert revoked(service) == [jti(access)]


def test_logout_rejects_a_refresh_token_of_another_user_and_revokes_nothing(monkeypatch):
    stub_blacklist(monkeypatch)
    me = make_user(id=1)
    someone_elses = create_token(2, "hash", TokenType.REFRESH)
    service = make_service(me)

    with pytest.raises(ValidationException) as exc_info:
        run(service.logout(create_token(1, "hash"), me, someone_elses))

    assert exc_info.value.code == "refresh_token_mismatch"
    assert revoked(service) == []
    assert service.db.commits == 0


# ---------- rotação do refresh token


def stub_revoke_once(monkeypatch, result):
    calls = []

    async def revoke_once(token, db):
        calls.append(token)
        return result

    monkeypatch.setattr(user_service, "revoke_token_once", revoke_once)
    return calls


def test_refresh_rotates_the_token_and_keeps_the_original_expiry(monkeypatch):
    me = make_user()
    # 2 dias, não os 7 padrão: uma renovação deslizante (7 dias) daria outra expiração.
    old = create_token(me.id, me.password_hash, TokenType.REFRESH, token_duration=timedelta(days=2))
    old_exp = unverified_claims(old)["exp"]
    calls = stub_revoke_once(monkeypatch, datetime.fromtimestamp(old_exp, tz=UTC))
    service = make_service(me)

    response = run(service.use_refresh_token(me, old))

    new_refresh = unverified_claims(response.refresh_token)
    assert calls == [old]  # o refresh usado foi revogado
    assert new_refresh["type"] == "refresh"
    assert new_refresh["jti"] != jti(old)
    assert new_refresh["exp"] == old_exp  # teto absoluto: renovar não estende a sessão
    assert unverified_claims(response.access_token)["type"] == "access"
    assert new_refresh["pwd"] == unverified_claims(old)["pwd"]
    assert service.db.commits == 1


def test_refresh_rejects_a_token_that_was_already_used_and_issues_nothing(monkeypatch):
    me = make_user()
    stub_revoke_once(monkeypatch, None)
    service = make_service(me)

    with pytest.raises(AuthenticationException) as exc_info:
        run(service.use_refresh_token(me, create_token(me.id, "hash", TokenType.REFRESH)))

    assert exc_info.value.code == "refresh_token_reused"
    assert service.db.commits == 0


# ---------- token de reset de uso único (impressão digital da senha atual)


def reset_with(service, token, new_password="Newpass12"):
    return run(
        service.reset_user_password(
            ResetPasswordRequest(reset_token=token, new_password=new_password)
        )
    )


def test_reset_token_can_be_used_only_once():
    me = make_user()
    service = make_service(me)
    token = create_reset_password_token(me.email, me.password_hash)

    reset_with(service, token)

    with pytest.raises(ValidationException) as exc_info:
        reset_with(service, token, new_password="Another123")
    assert exc_info.value.code == "invalid_reset_token"
    assert service.db.commits == 1


def test_reset_token_stops_working_when_the_password_changes_by_any_other_means():
    me = make_user()
    service = make_service(me)
    token = create_reset_password_token(me.email, me.password_hash)
    me.password_hash = bcrypt_context.hash("Changed123")  # ex.: reset anterior por outro e-mail

    with pytest.raises(ValidationException) as exc_info:
        reset_with(service, token)

    assert exc_info.value.code == "invalid_reset_token"
    assert service.db.commits == 0


def test_only_the_latest_reset_email_matters_after_a_reset():
    me = make_user()
    service = make_service(me)
    first = create_reset_password_token(me.email, me.password_hash)
    second = create_reset_password_token(me.email, me.password_hash)

    reset_with(service, first)

    with pytest.raises(ValidationException):
        reset_with(service, second)


def test_legacy_reset_token_without_password_fingerprint_is_rejected():
    me = make_user()
    legacy = jwt.encode(
        {"sub": me.email, "type": "reset_password", "exp": datetime.now(UTC) + timedelta(hours=1)},
        settings.SECRET_KEY,
        settings.ALGORITHM,
    )

    with pytest.raises(ValidationException):
        reset_with(make_service(me), legacy)


def test_reset_token_does_not_embed_the_password_hash():
    token = create_reset_password_token("a@b.co", PASSWORD_HASH)

    claims = unverified_claims(token)

    assert PASSWORD_HASH not in token
    assert PASSWORD_HASH not in claims.values()
    assert claims["pwd"]


def test_different_passwords_yield_different_reset_tokens_fingerprints():
    other_hash = bcrypt_context.hash(PASSWORD)
    claim = lambda h: unverified_claims(create_reset_password_token("a@b.co", h))["pwd"]

    assert claim(PASSWORD_HASH) != claim(other_hash)
    assert claim(PASSWORD_HASH) == claim(PASSWORD_HASH)


# ---------- anti-enumeração de contas


def forgot(service, email):
    tasks = BackgroundTasks()
    response = run(service.forgot_user_password(ForgotPasswordRequest(email=email), tasks))
    return response, tasks


def test_forgot_password_answers_identically_for_known_and_unknown_emails():
    service = make_service(make_user())

    known, _ = forgot(service, "maria@example.com")
    unknown, _ = forgot(service, "ghost@example.com")

    assert known == unknown


def test_forgot_password_only_sends_an_email_to_existing_accounts():
    service = make_service(make_user())

    _, known_tasks = forgot(service, "maria@example.com")
    _, unknown_tasks = forgot(service, "ghost@example.com")

    assert len(known_tasks.tasks) == 1
    assert len(unknown_tasks.tasks) == 0


def test_login_spends_hashing_time_even_when_the_account_does_not_exist(monkeypatch):
    calls = []
    monkeypatch.setattr(user_service.bcrypt_context, "dummy_verify", lambda: calls.append("dummy"))
    service = make_service(make_user())

    with pytest.raises(AuthenticationException):
        run(service.login(LoginRequest(email="ghost@example.com", password=PASSWORD)))

    assert calls == ["dummy"]


def test_login_with_a_real_account_does_not_need_the_dummy_hash(monkeypatch):
    calls = []
    monkeypatch.setattr(user_service.bcrypt_context, "dummy_verify", lambda: calls.append("dummy"))
    service = make_service(make_user())

    with pytest.raises(AuthenticationException):
        run(service.login(LoginRequest(email="maria@example.com", password="WrongPass1")))

    assert calls == []


def test_unknown_account_and_wrong_password_are_indistinguishable():
    service = make_service(make_user())

    errors = []
    for email in ("ghost@example.com", "maria@example.com"):
        with pytest.raises(AuthenticationException) as exc_info:
            run(service.login(LoginRequest(email=email, password="WrongPass1")))
        errors.append((exc_info.value.status_code, exc_info.value.code, exc_info.value.message))

    assert errors[0] == errors[1]
