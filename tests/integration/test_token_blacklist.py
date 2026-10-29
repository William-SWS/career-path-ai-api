"""A blacklist guarda só o jti, contra um Postgres real."""

import asyncio
from datetime import timedelta

import pytest
from sqlalchemy import text

from app.security.blacklist import add_token_to_blacklist, is_token_blacklisted, revoke_token_once
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
                await add_token_to_blacklist(token, session)
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
                await add_token_to_blacklist(revoked, session)
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
                await add_token_to_blacklist(unusable, session)
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
