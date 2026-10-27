from fastapi import APIRouter, Depends, Query
from app.schemas.development_trail_schema import (
    DevelopmentTrailRequest,
    DevelopmentTrailResponse,
    DevelopmentTrailListResponse,
    DevelopmentTrailUpdateRequest,
    DevelopmentTrailDeleteResponse,
)
from app.services.development_trail_services import DevelopmentTrailService
from app.utils.development_trail_utils import create_adaptive_development_trail_prompt
from app.models.user import User
from app.api.v1.dependencies.security import verify_token
from app.api.v1.dependencies.services import get_development_trail_service


router = APIRouter()


@router.post("/", response_model=DevelopmentTrailResponse)
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


@router.get("/test-prompt")
async def test_prompt_structure(current_user: User = Depends(verify_token)):
    """Endpoint para testar a estrutura do prompt (apenas desenvolvimento)"""
    test_data = DevelopmentTrailRequest(
        name="João Teste",
        age=25,
        education="Graduação em Sistemas de Informação",
        current_area="Desenvolvedor Júnior",
        experience_in_years=2,
        skills=["Python", "Django", "PostgreSQL"],
        interested_technologies=["Back-End", "DevOps"],
        current_level="Júnior",
        professional_goal="Tornar-se Desenvolvedor Pleno",
        available_time_week="20 horas semanais",
        goal_timeframe="8 meses",
        additional_information="Tenho interesse em aprender Docker e AWS",
    )

    prompt = create_adaptive_development_trail_prompt(test_data)

    return {
        "prompt_structure": "valid",
        "prompt_length": len(prompt),
        "has_user_data": True,
        "sample_prompt_preview": prompt[:500] + "..." if len(prompt) > 500 else prompt,
    }


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
