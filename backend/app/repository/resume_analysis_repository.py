from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.resume_analysis import ResumeAnalysis
from app.repository.base_repository import BaseRepository


class ResumeAnalysisRepository(BaseRepository[ResumeAnalysis]):
    def __init__(self, session: AsyncSession):
        super().__init__(ResumeAnalysis, session)

    async def get_by_user_id(
        self, user_id: int, skip: int = 0, limit: int = 100
    ) -> tuple[list[ResumeAnalysis], int]:
        """
        Busca análises por user_id com paginação e count total
        """
        # Busca as análises
        result = await self.session.execute(
            select(ResumeAnalysis)
            .where(ResumeAnalysis.user_id == user_id)
            .order_by(ResumeAnalysis.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        analyses = result.scalars().all()

        # Count total
        count_result = await self.session.execute(
            select(func.count(ResumeAnalysis.id)).where(ResumeAnalysis.user_id == user_id)
        )
        total_count = count_result.scalar_one()

        return analyses, total_count

    async def get_by_id_and_user_id(self, analysis_id: int, user_id: int) -> ResumeAnalysis | None:
        """
        Busca análise por ID e user_id (verificação de ownership)
        """
        result = await self.session.execute(
            select(ResumeAnalysis).where(
                ResumeAnalysis.id == analysis_id, ResumeAnalysis.user_id == user_id
            )
        )
        return result.scalar_one_or_none()
