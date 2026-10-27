from fastapi import HTTPException
from app.utils.development_trail_utils import (
    create_adaptive_development_trail_prompt,
    extract_json_from_response,
)
from app.schemas.development_trail_schema import (
    DevelopmentTrailRequest,
    DevelopmentTrailResponse,
    DevelopmentTrailListResponse,
    DevelopmentTrailUpdateRequest,
    DevelopmentTrailDeleteResponse
)
from app.models.user import User
from app.repository.development_trail_repository import DevelopmentTrailRepository
from app.core.config import settings
from app.core.logging_config import logger
from sqlalchemy.ext.asyncio import AsyncSession
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from datetime import datetime, timezone
from ..models.development_trail import DevelopmentTrailStatus


class DevelopmentTrailService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.development_trail_repository = DevelopmentTrailRepository(db)

    async def generate_development_trail_with_gemini_service(
        self, user_data: DevelopmentTrailRequest, current_user: User
    ) -> DevelopmentTrailResponse:
        """Serviço que gera trilha de desenvolvimento usando Google Gemini"""
        
        if not settings.GEMINI_API_KEY:
            raise HTTPException(
                status_code=500,
                detail="Serviço de IA indisponível no momento"
            )
        
        genai.configure(api_key=settings.GEMINI_API_KEY)
        
        # Cria prompt
        prompt = create_adaptive_development_trail_prompt(user_data)

        try:
            model = genai.GenerativeModel("gemini-2.5-flash")

            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.3, 
                    max_output_tokens=10000,  # Aumentado para prevenir truncamento
                    top_p=0.8, 
                    top_k=40
                ),
            )

            # Verifica se a resposta foi truncada
            if hasattr(response.candidates[0], 'finish_reason') and response.candidates[0].finish_reason == 'MAX_OUTPUT_TOKENS':
                logger.warning("Resposta do Gemini foi truncada devido ao limite de tokens")

            response_text = response.text.strip()
            logger.debug(f"Resposta bruta do Gemini (primeiros 500 chars): {response_text[:500]}")
            
            development_trail_result = extract_json_from_response(response_text)

            # Valida o resultado antes de salvar
            if not development_trail_result or not isinstance(development_trail_result, dict):
                raise ValueError("Resultado da trilha inválido ou vazio")

            # Verifica se tem pelo menos alguns campos esperados
            if not development_trail_result.get("user_profile_summary") and not development_trail_result.get("development_phases"):
                logger.warning("Resultado da trilha pode estar incompleto, mas prosseguindo...")

            development_trail = await self.development_trail_repository.create(
                user_id=current_user.id,
                development_trail=development_trail_result,
                status=DevelopmentTrailStatus.IN_PROGRESS.value,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            
            await self.db.commit()
            await self.db.refresh(development_trail)

            return DevelopmentTrailResponse(
                id=development_trail.id,
                development_trail=development_trail.development_trail,
                status=development_trail.status,
                created_at=development_trail.created_at,
                updated_at=development_trail.updated_at
            )

        except google_exceptions.ResourceExhausted:
            await self.db.rollback()
            logger.exception("Quota da API do Gemini excedida ao gerar trilha")
            raise HTTPException(
                status_code=429,
                detail="Limite de uso do serviço de IA excedido. Tente novamente em alguns minutos."
            )

        except ValueError as e:
            await self.db.rollback()
            raise HTTPException(status_code=400, detail=str(e))

        except HTTPException:
            await self.db.rollback()
            raise

        except Exception:
            await self.db.rollback()
            logger.exception("Erro ao gerar trilha de desenvolvimento")
            raise HTTPException(
                status_code=500,
                detail="Erro interno ao gerar trilha de desenvolvimento"
            )

    async def get_development_trail_service(
        self, current_user: User, skip: int, limit: int
    ) -> DevelopmentTrailListResponse:
        """
        Serviço que retorna todas as trilhas de desenvolvimento do usuário
        """
        try:
            development_trails, total_count = await self.development_trail_repository.get_by_user_id(
                user_id=current_user.id,
                skip=skip,
                limit=limit
            ) 

            if not development_trails:
                raise HTTPException(
                    status_code=404, detail="Nenhuma trilha de desenvolvimento encontrada"
                )
            
            return DevelopmentTrailListResponse(
                development_trails=development_trails, 
                total_count=total_count
            )
        
        except HTTPException:
            raise
        except Exception:
            logger.exception("Erro ao buscar trilhas de desenvolvimento")
            raise HTTPException(
                status_code=500,
                detail="Erro ao buscar trilhas de desenvolvimento"
            )

    async def get_development_trail_by_id_service(
        self, development_trail_id: int, current_user: User
    ) -> DevelopmentTrailResponse:
        """
        Serviço que retorna uma trilha de desenvolvimento específica do usuário
        """
        try:
            development_trail = await self.development_trail_repository.get_by_id_and_user_id(
                development_trail_id=development_trail_id,
                user_id=current_user.id
            ) 

            if not development_trail:
                raise HTTPException(
                    status_code=404,
                    detail="Trilha de desenvolvimento não encontrada"
                )
            
            return DevelopmentTrailResponse(
                id=development_trail.id,
                development_trail=development_trail.development_trail,
                status=development_trail.status,
                created_at=development_trail.created_at,
                updated_at=development_trail.updated_at
            )
        
        except HTTPException:
            raise
        except Exception:
            logger.exception("Erro ao buscar trilha de desenvolvimento")
            raise HTTPException(
                status_code=500,
                detail="Erro ao buscar trilha de desenvolvimento"
            )
        
    async def update_development_trail_status_service(
        self,
        development_trail_id: int,
        update_data: DevelopmentTrailUpdateRequest,
        current_user: User
    ) -> DevelopmentTrailResponse:
        """
        Serviço para atualizar o status de uma trilha de desenvolvimento
        """
        try:
            development_trail = await self.development_trail_repository.get_by_id_and_user_id(
                development_trail_id=development_trail_id,
                user_id=current_user.id
            )

            if not development_trail:
                raise HTTPException(
                    status_code=404, detail="Trilha de desenvolvimento não encontrada"
                )

            # Atualizar o status
            updated_trail = await self.development_trail_repository.update_status(
                development_trail_id=development_trail_id,
                status=update_data.status.value
            )
            
            await self.db.commit()
            await self.db.refresh(updated_trail)

            return DevelopmentTrailResponse(
                id=updated_trail.id,
                development_trail=updated_trail.development_trail,
                status=updated_trail.status,
                created_at=updated_trail.created_at,
                updated_at=updated_trail.updated_at
            )

        except HTTPException:
            raise
        except Exception:
            logger.exception("Erro ao atualizar status da trilha de desenvolvimento")
            await self.db.rollback()
            raise HTTPException(
                status_code=500,
                detail="Erro ao atualizar status da trilha de desenvolvimento"
            )
        
    async def delete_development_trail_service(
        self, development_trail_id: int, current_user: User
    ) -> DevelopmentTrailDeleteResponse:
        """
        Serviço para deletar uma trilha de desenvolvimento do usuário
        """
        try:
            development_trail = await self.development_trail_repository.get_by_id_and_user_id(
                development_trail_id=development_trail_id,
                user_id=current_user.id
            )

            if not development_trail:
                raise HTTPException(
                    status_code=404, detail="Trilha de desenvolvimento não encontrada"
                )
            
            await self.development_trail_repository.delete(development_trail_id)
            await self.db.commit()

            return DevelopmentTrailDeleteResponse(
                message="Trilha de desenvolvimento deletada com sucesso",
                deleted_id=development_trail_id,
            )

        except HTTPException:
            raise
        except Exception:
            logger.exception("Erro ao deletar trilha de desenvolvimento")
            await self.db.rollback()
            raise HTTPException(
                status_code=500,
                detail="Erro ao deletar trilha de desenvolvimento"
            )