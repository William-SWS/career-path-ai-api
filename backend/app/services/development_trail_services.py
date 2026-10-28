from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import release_connection
from app.core.exceptions import NotFoundException
from app.llm.client import LLMClient
from app.llm.responses import parse_structured_response
from app.models.user import User
from app.repository.development_trail_repository import DevelopmentTrailRepository
from app.schemas.ai_outputs import DevelopmentTrailOutput
from app.schemas.development_trail_schema import (
    DevelopmentTrailDeleteResponse,
    DevelopmentTrailListResponse,
    DevelopmentTrailRequest,
    DevelopmentTrailResponse,
    DevelopmentTrailUpdateRequest,
)
from app.utils.development_trail_utils import (
    DEVELOPMENT_TRAIL_PARAMS,
    create_adaptive_development_trail_prompt,
)

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
        updated_at=development_trail.updated_at,
    )


class DevelopmentTrailService:
    def __init__(self, db: AsyncSession, llm: LLMClient):
        self.db = db
        self.llm = llm
        self.development_trail_repository = DevelopmentTrailRepository(db)

    async def generate_development_trail_with_gemini_service(
        self, user_data: DevelopmentTrailRequest, current_user: User
    ) -> DevelopmentTrailResponse:
        """Serviço que gera trilha de desenvolvimento usando Google Gemini"""
        prompt = create_adaptive_development_trail_prompt(user_data)
        await release_connection(self.db)
        response_text = await self.llm.generate(
            prompt, DEVELOPMENT_TRAIL_PARAMS, response_schema=DevelopmentTrailOutput
        )
        development_trail_result = parse_structured_response(
            DevelopmentTrailOutput, response_text
        ).model_dump()

        development_trail = await self.development_trail_repository.create(
            user_id=current_user.id,
            development_trail=development_trail_result,
            status=DevelopmentTrailStatus.IN_PROGRESS.value,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
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
            user_id=current_user.id, skip=skip, limit=limit
        )

        return DevelopmentTrailListResponse(
            development_trails=development_trails, total_count=total_count
        )

    async def get_development_trail_by_id_service(
        self, development_trail_id: int, current_user: User
    ) -> DevelopmentTrailResponse:
        """
        Serviço que retorna uma trilha de desenvolvimento específica do usuário
        """
        development_trail = await self.development_trail_repository.get_by_id_and_user_id(
            development_trail_id=development_trail_id, user_id=current_user.id
        )

        if not development_trail:
            raise _trail_not_found()

        return _to_response(development_trail)

    async def update_development_trail_status_service(
        self,
        development_trail_id: int,
        update_data: DevelopmentTrailUpdateRequest,
        current_user: User,
    ) -> DevelopmentTrailResponse:
        """
        Serviço para atualizar o status de uma trilha de desenvolvimento
        """
        development_trail = await self.development_trail_repository.get_by_id_and_user_id(
            development_trail_id=development_trail_id, user_id=current_user.id
        )

        if not development_trail:
            raise _trail_not_found()

        updated_trail = await self.development_trail_repository.update_status(
            development_trail_id=development_trail_id, status=update_data.status.value
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
            development_trail_id=development_trail_id, user_id=current_user.id
        )

        if not development_trail:
            raise _trail_not_found()

        await self.development_trail_repository.delete(development_trail_id)
        await self.db.commit()

        return DevelopmentTrailDeleteResponse(
            message="Trilha de desenvolvimento deletada com sucesso",
            deleted_id=development_trail_id,
        )
