import asyncio
from datetime import datetime, timezone
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
from app.utils.token_utils import create_reset_password_token

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


def make_user(id=1, email="maria@example.com"):
    return SimpleNamespace(
        id=id,
        email=email,
        name="Maria Silva",
        password_hash=PASSWORD_HASH,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def make_service(*users):
    service = UserService(db=None)
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
