from datetime import UTC, datetime

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import release_connection
from app.core.exceptions import NotFoundException
from app.llm.client import LLMClient
from app.llm.responses import parse_structured_response
from app.models.user import User
from app.repository.resume_analysis_repository import ResumeAnalysisRepository
from app.schemas.ai_outputs import ResumeAnalysisOutput
from app.schemas.resume_analysis_schema import (
    ResumeAnalysisDeleteResponse,
    ResumeAnalysisListResponse,
    ResumeAnalysisResponse,
)
from app.utils.pdf_utils import check_pdf
from app.utils.resume_analysis_utils import (
    RESUME_ANALYSIS_PARAMS,
    build_resume_analysis_prompt,
)


def _analysis_not_found() -> NotFoundException:
    return NotFoundException("Análise não encontrada", code="resume_analysis_not_found")


class ResumeAnalysisService:
    def __init__(self, db: AsyncSession, llm: LLMClient):
        self.db = db
        self.llm = llm
        self.resume_analysis_repository = ResumeAnalysisRepository(db)

    async def analyze_resume_service(
        self, file: UploadFile, current_user: User,
    ) -> ResumeAnalysisResponse:
        """
        Service para análise de currículo
        """
        text = await check_pdf(file)

        prompt = build_resume_analysis_prompt(text)
        await release_connection(self.db)
        response_text = await self.llm.generate(
            prompt, RESUME_ANALYSIS_PARAMS, response_schema=ResumeAnalysisOutput
        )
        analysis_result = parse_structured_response(
            ResumeAnalysisOutput, response_text
        ).model_dump()

        # Salva no banco
        resume_analysis = await self.resume_analysis_repository.create(
            user_id=current_user.id,
            original_filename=file.filename,
            analysis_result=analysis_result,
            created_at=datetime.now(UTC)
        )

        await self.db.commit()
        await self.db.refresh(resume_analysis)

        return ResumeAnalysisResponse(
            id=resume_analysis.id,
            original_filename=resume_analysis.original_filename,
            analysis_result=resume_analysis.analysis_result,
            created_at=resume_analysis.created_at
        )

    async def get_resume_analysis_service(
        self, current_user: User, skip: int, limit: int
    ) -> ResumeAnalysisListResponse:
        """
        Serviço para obter todas as análises de currículo do usuário
        """
        analyses, total_count = await self.resume_analysis_repository.get_by_user_id(
            user_id=current_user.id,
            skip=skip,
            limit=limit
        )

        # Converte cada análise, tratando casos onde analysis_result pode ser None
        analyses_response = [
            ResumeAnalysisResponse(
                id=analysis.id,
                original_filename=analysis.original_filename or "",
                analysis_result=analysis.analysis_result if analysis.analysis_result is not None else {},
                created_at=analysis.created_at
            )
            for analysis in (analyses or [])
        ]

        return ResumeAnalysisListResponse(
            analyses=analyses_response,
            total_count=total_count
        )

    async def get_resume_analysis_by_id_service(
        self, analysis_id: int, current_user: User
    ) -> ResumeAnalysisResponse:
        """
        Serviço para obter uma análise de currículo específica do usuário
        """
        analysis = await self.resume_analysis_repository.get_by_id_and_user_id(
            analysis_id=analysis_id,
            user_id=current_user.id
        )

        if not analysis:
            raise _analysis_not_found()

        return ResumeAnalysisResponse(
            id=analysis.id,
            original_filename=analysis.original_filename,
            analysis_result=analysis.analysis_result,
            created_at=analysis.created_at
        )

    async def delete_resume_analysis_service(
            self, analysis_id: int, current_user: User
    ) -> ResumeAnalysisDeleteResponse:
        """
        Serviço para deletar uma análise de currículo do usuário
        """
        analysis = await self.resume_analysis_repository.get_by_id_and_user_id(
            analysis_id=analysis_id,
            user_id=current_user.id
        )

        if not analysis:
            raise _analysis_not_found()

        await self.resume_analysis_repository.delete(analysis.id)
        await self.db.commit()

        return ResumeAnalysisDeleteResponse(
            message="Análise deletada com sucesso",
            deleted_id=analysis_id
        )
