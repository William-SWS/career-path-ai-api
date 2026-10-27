from fastapi import HTTPException, UploadFile
from app.models.user import User
from app.utils.interview_guide_utils import generate_interview_guide_with_gemini
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


class InterviewGuideService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.interview_guide_repository = InterviewGuideRepository(db)

    async def generate_interview_guide_service(self, file: UploadFile, job_description: str, current_user: User) -> InterviewGuideResponse:
        """
        Service para geração de guia de entrevista
        """
        try:
            resume_text = await check_pdf(file)

            # Gera o guia de entrevista com Gemini
            interview_guide_result = await generate_interview_guide_with_gemini(resume_text, job_description)

            # Valida o resultado antes de salvar
            if not interview_guide_result or not isinstance(interview_guide_result, dict):
                raise ValueError("Resultado do guia de entrevista inválido ou vazio")

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

        except ValueError as e:
            await self.db.rollback()
            raise HTTPException(status_code=400, detail=str(e))
        except HTTPException:
            await self.db.rollback()
            raise
        except Exception:
            logger.exception("Erro ao gerar guia de entrevista")
            await self.db.rollback()
            raise HTTPException(
                status_code=500, detail="Erro ao gerar guia de entrevista"
            )
        
    async def get_interview_guide_service(self, current_user: User, skip: int, limit: int) -> InterviewGuideListResponse:
        """
        Serviço para obter guias de entrevista do usuário
        """
        try:
            interview_guides, total_count = await self.interview_guide_repository.get_by_user_id(
                user_id=current_user.id,
                skip=skip,
                limit=limit
            )

            return InterviewGuideListResponse(
                interview_guides=interview_guides,
                total_count=total_count
            )
        
        except Exception:
            logger.exception("Erro ao buscar análises")
            raise HTTPException(
                status_code=500,
                detail="Erro ao buscar análises"
            )
        
    async def get_interview_guide_by_id_service(
        self, interview_guide_id: int, current_user: User
    ) -> InterviewGuideResponse:
        """
        Serviço para obter um guia de entrevista específico do usuário        
        """
        try:
            interview_guide = await self.interview_guide_repository.get_by_id_and_user_id(
                interview_guide_id=interview_guide_id,
                user_id=current_user.id
            )
            
            if not interview_guide:
                raise HTTPException(
                    status_code=404,
                    detail="Guia de entrevista não encontrado"
                )
            
            if interview_guide.interview_guide is None:
                interview_guide.interview_guide = {}
            
            return InterviewGuideResponse(
                id=interview_guide.id,
                interview_guide=interview_guide.interview_guide
            )
        except HTTPException:
            raise
        except Exception:
            logger.exception("Erro ao buscar guia de entrevista")
            raise HTTPException(
                status_code=500,
                detail="Erro ao buscar guia de entrevista"
            )
    
    async def delete_interview_guide_service(
        self, interview_guide_id: int, current_user: User
    ) -> InterviewGuideDeleteResponse:
        """
        Serviço para deletar um guia de entrevista do usuário
        """
        try:
            interview_guide = await self.interview_guide_repository.get_by_id_and_user_id(
                interview_guide_id=interview_guide_id,
                user_id=current_user.id
            )

            if not interview_guide:
                raise HTTPException(
                    status_code=404,
                    detail="Guia de entrevista não encontrado"
                )
            
            await self.interview_guide_repository.delete(interview_guide.id)
            await self.db.commit()

            return InterviewGuideDeleteResponse(
                message="Guia de entrevista deletado com sucesso",
                deleted_id=interview_guide_id
            )
        
        except HTTPException:
            await self.db.rollback()
            raise
        except Exception:
            logger.exception("Erro ao deletar guia de entrevista")
            await self.db.rollback()
            raise HTTPException(
                status_code=500,
                detail="Erro ao deletar guia de entrevista"
            )