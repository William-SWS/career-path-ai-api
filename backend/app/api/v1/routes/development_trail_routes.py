from fastapi import APIRouter, Depends, Query

from app.api.v1.dependencies.rate_limit import limit_ai_generation
from app.api.v1.dependencies.security import verify_token
from app.api.v1.dependencies.services import get_development_trail_service
from app.models.user import User
from app.schemas.development_trail_schema import (
    DevelopmentTrailDeleteResponse,
    DevelopmentTrailListResponse,
    DevelopmentTrailRequest,
    DevelopmentTrailResponse,
    DevelopmentTrailUpdateRequest,
)
from app.services.development_trail_services import DevelopmentTrailService

router = APIRouter()


@router.post("/", response_model=DevelopmentTrailResponse, dependencies=[Depends(limit_ai_generation)])
async def generate_development_trail(
    user_data: DevelopmentTrailRequest,
    current_user: User = Depends(verify_token),
    development_trail_service: DevelopmentTrailService = Depends(get_development_trail_service)
):
    """
    Recebe dados do usuário e retorna trilha de desenvolvimento personalizada.
    """
    development_trail = await development_trail_service.generate_development_trail_with_gemini_service(
        user_data, current_user
    )
    return development_trail


@router.get("/", response_model=DevelopmentTrailListResponse)
async def get_my_development_trails(
    current_user: User = Depends(verify_token),
    skip: int = Query(0, ge=0, description="Número de itens para pular"),
    limit: int = Query(
        100, ge=1, le=100, description="Número máximo de itens por página"
    ),
    development_trail_service: DevelopmentTrailService = Depends(get_development_trail_service)
):
    """
    Retorna todas as trilhas de desenvolvimento do usuário autenticado.
    """
    development_trails = await development_trail_service.get_development_trail_service(
        current_user, skip, limit
    )
    return development_trails


@router.get(
    "/{development_trail_id}", response_model=DevelopmentTrailResponse
)
async def get_development_trail(
    development_trail_id: int,
    current_user: User = Depends(verify_token),
    development_trail_service: DevelopmentTrailService = Depends(get_development_trail_service)
):
    """
    Retorna uma trilha de desenvolvimento específica do usuário
    """
    development_trail = await development_trail_service.get_development_trail_by_id_service(
        development_trail_id, current_user
    )
    return development_trail


@router.patch(
    "/{development_trail_id}", response_model=DevelopmentTrailResponse
)
async def update_development_trail(
    development_trail_id: int,
    update_data: DevelopmentTrailUpdateRequest,
    current_user: User = Depends(verify_token),
    development_trail_service: DevelopmentTrailService = Depends(get_development_trail_service)
):
    """
    Atualiza o status de uma trilha de desenvolvimento.
    Status permitidos: "In Progress", "Completed"
    """
    development_trail = await development_trail_service.update_development_trail_status_service(
        development_trail_id, update_data, current_user
    )
    return development_trail


@router.delete(
    "/{development_trail_id}", response_model=DevelopmentTrailDeleteResponse
)
async def delete_development_trail(
    development_trail_id: int,
    current_user: User = Depends(verify_token),
    development_trail_service: DevelopmentTrailService = Depends(get_development_trail_service)
):
    """
    Deleta uma trilha de desenvolvimento do usuário.
    """
    result = await development_trail_service.delete_development_trail_service(
        development_trail_id, current_user
    )
    return result
