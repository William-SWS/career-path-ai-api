"""Fronteira transacional contra um Postgres real, com as migrations aplicadas."""
import asyncio
from types import SimpleNamespace

import pytest
from app.core.security import bcrypt_context, create_token, is_token_blacklisted
from app.repository.development_trail_repository import DevelopmentTrailRepository
from app.repository.user_repository import UserRepository
from app.schemas.auth_schema import RegisterRequest, ResetPasswordRequest
from app.schemas.development_trail_schema import DevelopmentTrailUpdateRequest
from app.services.development_trail_services import DevelopmentTrailService
from app.services.user_services import UserService
from app.utils.token_utils import create_reset_password_token
from tests.integration.conftest import open_sessions

pytestmark = pytest.mark.integration


def run(coro):
    return asyncio.run(coro)


async def _create_user(session, email="maria@example.com"):
    return await UserRepository(session).create(
        name="Maria Silva", email=email, password_hash=bcrypt_context.hash("Abcdef12")
    )


def test_repository_write_is_invisible_to_others_until_the_use_case_commits():
    async def scenario():
        async with open_sessions() as sessions:
            async with sessions() as writer, sessions() as reader:
                user = await _create_user(writer)
                email = user.email
                assert user.id is not None  # flush já gerou o id e os defaults

                assert await UserRepository(reader).get_by_email(email) is None
                await writer.commit()
                assert await UserRepository(reader).get_by_email(email) is not None

    run(scenario())


def test_rollback_discards_repository_writes():
    async def scenario():
        async with open_sessions() as sessions:
            async with sessions() as writer, sessions() as reader:
                await _create_user(writer)
                await writer.rollback()

                assert await UserRepository(reader).get_by_email("maria@example.com") is None

    run(scenario())


def test_register_persists_the_user_with_a_hashed_password():
    async def scenario():
        async with open_sessions() as sessions:
            async with sessions() as session, sessions() as reader:
                await UserService(session).create_user_account(
                    RegisterRequest(name="Maria Silva", email="maria@example.com", password="Abcdef12")
                )

                stored = await UserRepository(reader).get_by_email("maria@example.com")
                assert stored is not None
                assert bcrypt_context.verify("Abcdef12", stored.password_hash)

    run(scenario())


def test_logout_really_blacklists_the_token():
    async def scenario():
        async with open_sessions() as sessions:
            async with sessions() as session, sessions() as reader:
                token = create_token(1)

                await UserService(session).logout(token, SimpleNamespace(id=1))

                assert await is_token_blacklisted(token, reader)

    run(scenario())


def test_reset_password_persists_the_new_hash():
    async def scenario():
        async with open_sessions() as sessions:
            async with sessions() as setup:
                created = await _create_user(setup)
                email, password_hash = created.email, created.password_hash
                await setup.commit()
            async with sessions() as session, sessions() as reader:
                token = create_reset_password_token(email, password_hash)

                await UserService(session).reset_user_password(
                    ResetPasswordRequest(reset_token=token, new_password="Newpass12")
                )

                stored = await UserRepository(reader).get_by_email(email)
                assert bcrypt_context.verify("Newpass12", stored.password_hash)

    run(scenario())


def test_trail_status_update_is_committed_by_the_service():
    async def scenario():
        async with open_sessions() as sessions:
            async with sessions() as setup:
                user_id = (await _create_user(setup)).id
                trail_id = (await DevelopmentTrailRepository(setup).create(
                    user_id=user_id, development_trail={"a": 1}, status="In Progress"
                )).id
                await setup.commit()
            async with sessions() as session, sessions() as reader:
                owner = SimpleNamespace(id=user_id)
                response = await DevelopmentTrailService(session).update_development_trail_status_service(
                    trail_id, DevelopmentTrailUpdateRequest(status="Completed"), owner
                )
                assert response.status == "Completed"

                stored = await DevelopmentTrailRepository(reader).get_by_id(trail_id)
                assert stored.status == "Completed"

    run(scenario())
