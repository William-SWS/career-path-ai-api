"""A blacklist guarda só o jti, contra um Postgres real."""

import asyncio
from datetime import timedelta

import pytest
from sqlalchemy import text

from app.security.blacklist import (
    is_token_blacklisted,
    purge_expired_tokens,
    revoke_token_once,
)
from app.security.tokens import TokenType, create_token
from tests.fakes import unverified_claims
from tests.integration.conftest import open_sessions

pytestmark = pytest.mark.integration


def run(coro):
    return asyncio.run(coro)


def test_blacklist_stores_the_jti_and_never_the_token():
    token = create_token(1, "hash")

    async def scenario():
        async with open_sessions() as sessions:
            async with sessions() as session:
                await revoke_token_once(token, session)
                await session.commit()
            async with sessions() as reader:
                columns = (
                    (
                        await reader.execute(
                            text(
                                "SELECT column_name FROM information_schema.columns "
                                "WHERE table_name = 'token_blacklist'"
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                rows = (
                    (await reader.execute(text("SELECT jti FROM token_blacklist"))).scalars().all()
                )
        return columns, rows

    columns, rows = run(scenario())

    assert "token" not in columns
    assert rows == [unverified_claims(token)["jti"]]
    assert token not in rows


def test_only_the_revoked_token_is_blacklisted():
    revoked, other = create_token(1, "hash"), create_token(1, "hash")

    async def scenario():
        async with open_sessions() as sessions:
            async with sessions() as session:
                await revoke_token_once(revoked, session)
                await session.commit()
            async with sessions() as reader:
                return (
                    await is_token_blacklisted(revoked, reader),
                    await is_token_blacklisted(other, reader),
                )

    assert run(scenario()) == (True, False)


@pytest.mark.parametrize(
    "unusable",
    [create_token(1, "hash", TokenType.REFRESH, token_duration=timedelta(seconds=-5)), "garbage"],
    ids=["expired", "garbage"],
)
def test_invalid_or_expired_tokens_are_not_stored(unusable):
    async def scenario():
        async with open_sessions() as sessions:
            async with sessions() as session:
                await revoke_token_once(unusable, session)
                await session.commit()
                count = (
                    await session.execute(text("SELECT count(*) FROM token_blacklist"))
                ).scalar()
                return count, await is_token_blacklisted(unusable, session)

    assert run(scenario()) == (0, False)


def test_concurrent_revocations_of_the_same_token_have_exactly_one_winner():
    token = create_token(1, "hash", TokenType.REFRESH)

    async def revoke(sessions):
        async with sessions() as session:
            result = await revoke_token_once(token, session)
            await session.commit()
            return result

    async def scenario():
        async with open_sessions() as sessions:
            return await asyncio.gather(*(revoke(sessions) for _ in range(8)))

    results = run(scenario())

    assert len([r for r in results if r is not None]) == 1  # os outros 7 perderam a corrida


def test_revoke_once_refuses_invalid_or_already_revoked_tokens():
    token = create_token(1, "hash", TokenType.REFRESH)

    async def scenario():
        async with open_sessions() as sessions:
            async with sessions() as session:
                first = await revoke_token_once(token, session)
                await session.commit()
                second = await revoke_token_once(token, session)
                garbage = await revoke_token_once("garbage", session)
                return first, second, garbage

    first, second, garbage = run(scenario())

    assert first is not None
    assert second is None
    assert garbage is None


async def insert_rows(session, *, expired: int, valid: int = 0):
    for i in range(expired):
        await session.execute(
            text(
                "INSERT INTO token_blacklist (jti, expires_at) "
                "VALUES (:jti, now() - interval '1 hour')"
            ),
            {"jti": f"expired-{i}"},
        )
    for i in range(valid):
        await session.execute(
            text(
                "INSERT INTO token_blacklist (jti, expires_at) "
                "VALUES (:jti, now() + interval '1 hour')"
            ),
            {"jti": f"valid-{i}"},
        )
    await session.commit()


async def stored_jtis(session) -> set[str]:
    return set((await session.execute(text("SELECT jti FROM token_blacklist"))).scalars())


def test_revoking_a_token_purges_expired_rows_and_keeps_the_valid_ones():
    token = create_token(1, "hash")

    async def scenario():
        async with open_sessions() as sessions:
            async with sessions() as session:
                await insert_rows(session, expired=3, valid=2)
                await revoke_token_once(token, session)
                await session.commit()
            async with sessions() as reader:
                return await stored_jtis(reader)

    jtis = run(scenario())

    assert jtis == {"valid-0", "valid-1", unverified_claims(token)["jti"]}


def test_purge_removes_at_most_one_batch_per_call():
    async def scenario():
        async with open_sessions() as sessions:
            async with sessions() as session:
                await insert_rows(session, expired=5)
                first = await purge_expired_tokens(session, limit=2)
                await session.commit()
                second = await purge_expired_tokens(session, limit=10)
                await session.commit()
            return first, second

    assert run(scenario()) == (2, 3)


def test_concurrent_purges_do_not_wait_for_each_other():
    async def scenario():
        async with open_sessions() as sessions:
            async with sessions() as seed:
                await insert_rows(seed, expired=3)
            async with sessions() as first, sessions() as second:
                taken = await purge_expired_tokens(first)  # sem commit: segura as linhas
                # Com `FOR UPDATE` simples a segunda esperaria o commit da primeira.
                skipped = await asyncio.wait_for(purge_expired_tokens(second), timeout=5)
                await first.commit()
                await second.commit()
            return taken, skipped

    assert run(scenario()) == (3, 0)


def test_logout_succeeds_while_another_request_is_revoking_the_same_tokens():
    """Duas revogações simultâneas do mesmo token: a que chega depois não pode virar 500."""
    from types import SimpleNamespace

    from app.services.user_service import UserService

    access = create_token(1, "hash")
    refresh = create_token(1, "hash", TokenType.REFRESH)

    async def scenario():
        async with open_sessions() as sessions:
            async with sessions() as other, sessions() as mine, sessions() as reader:
                # A outra requisição já inseriu os dois, sem commit: a nossa espera o commit dela.
                await revoke_token_once(access, other)
                await revoke_token_once(refresh, other)
                logout = asyncio.create_task(
                    UserService(mine).logout(access, SimpleNamespace(id=1), refresh)
                )
                await asyncio.sleep(0.3)
                assert not logout.done()  # bloqueada pela linha ainda não confirmada
                await other.commit()
                result = await asyncio.wait_for(logout, timeout=5)
                count = (
                    await reader.execute(text("SELECT count(*) FROM token_blacklist"))
                ).scalar()
                return result, count, await is_token_blacklisted(access, reader)

    result, count, blacklisted = run(scenario())

    assert result.message == "Logout realizado com sucesso"
    assert count == 2  # um por token, sem duplicar
    assert blacklisted
