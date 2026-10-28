from typing import Generic, TypeVar, cast

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.core.database import Base

ModelType = TypeVar("ModelType", bound=Base)


def _id_column(model: type[Base]) -> InstrumentedAttribute[int]:
    """Coluna `id` do modelo: todos os modelos que usam este repositório têm uma."""
    return cast("InstrumentedAttribute[int]", model.id)  # type: ignore[attr-defined]


class BaseRepository(Generic[ModelType]):
    def __init__(self, model: type[ModelType], session: AsyncSession):
        self.model = model
        self.session = session

    async def get_by_id(self, id: int) -> ModelType | None:
        result = await self.session.execute(select(self.model).where(_id_column(self.model) == id))
        return result.scalar_one_or_none()

    async def get_all(self, skip: int = 0, limit: int = 100) -> list[ModelType]:
        result = await self.session.execute(select(self.model).offset(skip).limit(limit))
        return list(result.scalars().all())

    # Os métodos de escrita só fazem flush: o commit (e o rollback) pertencem ao
    # caso de uso, que sabe quando a operação como um todo terminou.
    async def create(self, **kwargs) -> ModelType:
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def update(self, id: int, **kwargs) -> ModelType | None:
        obj = await self.get_by_id(id)
        if not obj:
            return None

        for key, value in kwargs.items():
            setattr(obj, key, value)

        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def delete(self, id: int) -> None:
        await self.session.execute(delete(self.model).where(_id_column(self.model) == id))
        await self.session.flush()
