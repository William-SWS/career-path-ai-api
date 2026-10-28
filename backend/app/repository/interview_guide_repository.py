
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.interview_guide import InterviewGuide
from app.repository.base_repository import BaseRepository


class InterviewGuideRepository(BaseRepository[InterviewGuide]):
    def __init__(self, session: AsyncSession):
        super().__init__(InterviewGuide, session)

    async def get_by_user_id(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> tuple[list[InterviewGuide], int]:
        """
        Busca guias de entrevista por user_id com paginação e count total
        """
        result = await self.session.execute(
            select(InterviewGuide)
            .where(InterviewGuide.user_id == user_id)
            .order_by(InterviewGuide.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        interview_guides = result.scalars().all()

        count_result = await self.session.execute(
            select(func.count(InterviewGuide.id))
            .where(InterviewGuide.user_id == user_id)
        )
        total_count = count_result.scalar_one()

        return interview_guides, total_count

    async def get_by_id_and_user_id(
        self,
        interview_guide_id: int,
        user_id: int
    ) -> InterviewGuide | None:
        """
        Busca guia de entrevista por ID e user_id
        """
        result = await self.session.execute(
            select(InterviewGuide)
            .where(
                InterviewGuide.id == interview_guide_id,
                InterviewGuide.user_id == user_id
            )
        )
        return result.scalar_one_or_none()
