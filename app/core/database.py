from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    pass


# Engine assincrono (para FastAPI)
async_engine = create_async_engine(
    settings.DATABASE_URI,
    echo=settings.DEBUG,
)

AsyncSessionLocal = async_sessionmaker(
    autocommit=False, autoflush=False, bind=async_engine, class_=AsyncSession
)


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def release_connection(db: AsyncSession) -> None:
    """Devolve a conexão ao pool antes de uma espera longa que não usa o banco (ex.: LLM).

    A autenticação já fez consultas na sessão, e a transação aberta seguraria a
    conexão durante toda a espera. `close()` encerra a transação e solta os objetos
    (que continuam legíveis); a sessão reabre uma conexão na próxima consulta.
    """
    await db.close()
