from fastapi import UploadFile
from app.core.exceptions import NotFoundException
from app.llm.client import LLMClient
from app.llm.responses import parse_json_response
from app.models.user import User
from app.utils.interview_guide_utils import (
    INTERVIEW_GUIDE_PARAMS,
    build_interview_guide_prompt,
    extract_interview_json_from_text,
)
from app.schemas.interview_guide_schema import (
    InterviewGuideResponse, 
    InterviewGuideListResponse,
    InterviewGuideDeleteResponse
)
from app.utils.pdf_utils import check_pdf
from app.repository.interview_guide_repository import InterviewGuideRepository
from app.core.logging_config import logger
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone


def _guide_not_found() -> NotFoundException:
    return NotFoundException(
        "Guia de entrevista não encontrado", code="interview_guide_not_found"
    )


class InterviewGuideService:
    def __init__(self, db: AsyncSession, llm: LLMClient):
        self.db = db
        self.llm = llm
        self.interview_guide_repository = InterviewGuideRepository(db)

    async def generate_interview_guide_service(self, file: UploadFile, job_description: str, current_user: User) -> InterviewGuideResponse:
        """
        Service para geração de guia de entrevista
        """
        resume_text = await check_pdf(file)

        prompt = build_interview_guide_prompt(resume_text, job_description)
        response_text = await self.llm.generate(prompt, INTERVIEW_GUIDE_PARAMS)
        interview_guide_result = parse_json_response(extract_interview_json_from_text, response_text)

        # Verifica se tem pelo menos alguns campos esperados
        if not interview_guide_result.get("preparation_overview") and not interview_guide_result.get("technical_preparation"):
            logger.warning("Resultado do guia pode estar incompleto, mas prosseguindo...")

        interview_guide = await self.interview_guide_repository.create(
            user_id=current_user.id,
            interview_guide=interview_guide_result,
            created_at=datetime.now(timezone.utc)
        )

        await self.db.commit()
        await self.db.refresh(interview_guide)

        return InterviewGuideResponse(
            id=interview_guide.id,
            interview_guide=interview_guide_result
        )

    async def get_interview_guide_service(self, current_user: User, skip: int, limit: int) -> InterviewGuideListResponse:
        """
        Serviço para obter guias de entrevista do usuário
        """
        interview_guides, total_count = await self.interview_guide_repository.get_by_user_id(
            user_id=current_user.id,
            skip=skip,
            limit=limit
        )

        return InterviewGuideListResponse(
            interview_guides=interview_guides,
            total_count=total_count
        )

    async def get_interview_guide_by_id_service(
        self, interview_guide_id: int, current_user: User
    ) -> InterviewGuideResponse:
        """
        Serviço para obter um guia de entrevista específico do usuário        
        """
        interview_guide = await self.interview_guide_repository.get_by_id_and_user_id(
            interview_guide_id=interview_guide_id,
            user_id=current_user.id
        )

        if not interview_guide:
            raise _guide_not_found()

        return InterviewGuideResponse(
            id=interview_guide.id,
            interview_guide=interview_guide.interview_guide or {}
        )

    async def delete_interview_guide_service(
        self, interview_guide_id: int, current_user: User
    ) -> InterviewGuideDeleteResponse:
        """
        Serviço para deletar um guia de entrevista do usuário
        """
        interview_guide = await self.interview_guide_repository.get_by_id_and_user_id(
            interview_guide_id=interview_guide_id,
            user_id=current_user.id
        )

        if not interview_guide:
            raise _guide_not_found()

        await self.interview_guide_repository.delete(interview_guide.id)
        await self.db.commit()

        return InterviewGuideDeleteResponse(
            message="Guia de entrevista deletado com sucesso",
            deleted_id=interview_guide_id
        )
