from app.core.exceptions import ExternalServiceException, NotFoundException
from app.utils.development_trail_utils import generate_development_trail_with_gemini
from app.schemas.development_trail_schema import (
    DevelopmentTrailRequest,
    DevelopmentTrailResponse,
    DevelopmentTrailListResponse,
    DevelopmentTrailUpdateRequest,
    DevelopmentTrailDeleteResponse
)
from app.models.user import User
from app.repository.development_trail_repository import DevelopmentTrailRepository
from app.core.logging_config import logger
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
from ..models.development_trail import DevelopmentTrailStatus


def _trail_not_found() -> NotFoundException:
    return NotFoundException(
        "Trilha de desenvolvimento não encontrada", code="development_trail_not_found"
    )


def _to_response(development_trail) -> DevelopmentTrailResponse:
    return DevelopmentTrailResponse(
        id=development_trail.id,
        development_trail=development_trail.development_trail,
        status=development_trail.status,
        created_at=development_trail.created_at,
        updated_at=development_trail.updated_at
    )


class DevelopmentTrailService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.development_trail_repository = DevelopmentTrailRepository(db)

    async def generate_development_trail_with_gemini_service(
        self, user_data: DevelopmentTrailRequest, current_user: User
    ) -> DevelopmentTrailResponse:
        """Serviço que gera trilha de desenvolvimento usando Google Gemini"""
        development_trail_result = await generate_development_trail_with_gemini(user_data)

        # Valida o resultado antes de salvar
        if not development_trail_result or not isinstance(development_trail_result, dict):
            raise ExternalServiceException(
                "O serviço de IA devolveu uma resposta inválida", code="ai_invalid_response"
            )

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

        return _to_response(development_trail)

    async def get_development_trail_service(
        self, current_user: User, skip: int, limit: int
    ) -> DevelopmentTrailListResponse:
        """
        Serviço que retorna todas as trilhas de desenvolvimento do usuário
        """
        development_trails, total_count = await self.development_trail_repository.get_by_user_id(
            user_id=current_user.id,
            skip=skip,
            limit=limit
        )

        return DevelopmentTrailListResponse(
            development_trails=development_trails,
            total_count=total_count
        )

    async def get_development_trail_by_id_service(
        self, development_trail_id: int, current_user: User
    ) -> DevelopmentTrailResponse:
        """
        Serviço que retorna uma trilha de desenvolvimento específica do usuário
        """
        development_trail = await self.development_trail_repository.get_by_id_and_user_id(
            development_trail_id=development_trail_id,
            user_id=current_user.id
        )

        if not development_trail:
            raise _trail_not_found()

        return _to_response(development_trail)

    async def update_development_trail_status_service(
        self,
        development_trail_id: int,
        update_data: DevelopmentTrailUpdateRequest,
        current_user: User
    ) -> DevelopmentTrailResponse:
        """
        Serviço para atualizar o status de uma trilha de desenvolvimento
        """
        development_trail = await self.development_trail_repository.get_by_id_and_user_id(
            development_trail_id=development_trail_id,
            user_id=current_user.id
        )

        if not development_trail:
            raise _trail_not_found()

        updated_trail = await self.development_trail_repository.update_status(
            development_trail_id=development_trail_id,
            status=update_data.status.value
        )

        await self.db.commit()
        await self.db.refresh(updated_trail)

        return _to_response(updated_trail)

    async def delete_development_trail_service(
        self, development_trail_id: int, current_user: User
    ) -> DevelopmentTrailDeleteResponse:
        """
        Serviço para deletar uma trilha de desenvolvimento do usuário
        """
        development_trail = await self.development_trail_repository.get_by_id_and_user_id(
            development_trail_id=development_trail_id,
            user_id=current_user.id
        )

        if not development_trail:
            raise _trail_not_found()

        await self.development_trail_repository.delete(development_trail_id)
        await self.db.commit()

        return DevelopmentTrailDeleteResponse(
            message="Trilha de desenvolvimento deletada com sucesso",
            deleted_id=development_trail_id,
        )
