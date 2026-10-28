from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import Session, sessionmaker, DeclarativeBase
from sqlalchemy import create_engine
from app.core.config import settings

class Base(DeclarativeBase):
    pass

# Engine assincrono (para FastAPI)
async_engine = create_async_engine(
    settings.DATABASE_URI,
    echo=settings.DEBUG,
)

# Engine sincrono (para APScheduler)
sync_engine = create_engine(
    settings.DATABASE_URI.replace("postgresql+asyncpg://", "postgresql://"),
    echo=settings.DEBUG,
)

# Cria SessionLocal
AsyncSessionLocal = async_sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=async_engine,
    class_=AsyncSession
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=sync_engine,
    class_=Session
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


def get_db_sync():
    """
    Dependency para obter uma sessão de banco de dados síncrona
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
