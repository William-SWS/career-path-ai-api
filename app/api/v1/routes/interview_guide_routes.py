from fastapi import APIRouter, Depends, File, Form, Query, UploadFile

from app.api.v1.dependencies.rate_limit import limit_ai_generation
from app.api.v1.dependencies.security import verify_token
from app.api.v1.dependencies.services import get_interview_guide_service
from app.models.user import User
from app.schemas.interview_guide_schema import (
    InterviewGuideDeleteResponse,
    InterviewGuideListResponse,
    InterviewGuideResponse,
)
from app.services.interview_guide_services import InterviewGuideService

router = APIRouter()


@router.post(
    "/", response_model=InterviewGuideResponse, dependencies=[Depends(limit_ai_generation)]
)
async def generate_interview_guide(
    file: UploadFile = File(...),
    job_description: str = Form(..., min_length=1, max_length=5000),
    current_user: User = Depends(verify_token),
    interview_guide_service: InterviewGuideService = Depends(get_interview_guide_service),
):
    """
    Gera um roteiro detalhado para entrevista baseado no currículo e descrição da vaga
    """
    interview_guide = await interview_guide_service.generate_interview_guide_service(
        file, job_description, current_user
    )
    return interview_guide


@router.get("/", response_model=InterviewGuideListResponse)
async def get_my_interview_guides(
    current_user: User = Depends(verify_token),
    skip: int = Query(0, ge=0, description="Número de itens para pular"),
    limit: int = Query(100, ge=1, le=100, description="Número máximo de itens por página"),
    interview_guide_service: InterviewGuideService = Depends(get_interview_guide_service),
):
    """
    Retorna todos os interview_guides do usuário autenticado.
    """
    interview_guides = await interview_guide_service.get_interview_guide_service(
        current_user, skip, limit
    )
    return interview_guides


@router.get("/{interview_guide_id}", response_model=InterviewGuideResponse)
async def get_interview_guide(
    interview_guide_id: int,
    current_user: User = Depends(verify_token),
    interview_guide_service: InterviewGuideService = Depends(get_interview_guide_service),
):
    """
    Retorna um guia de entrevista específico do usuário.
    """
    interview_guide = await interview_guide_service.get_interview_guide_by_id_service(
        interview_guide_id, current_user
    )
    return interview_guide


@router.delete("/{interview_guide_id}", response_model=InterviewGuideDeleteResponse)
async def delete_interview_guide(
    interview_guide_id: int,
    current_user: User = Depends(verify_token),
    interview_guide_service: InterviewGuideService = Depends(get_interview_guide_service),
):
    """
    Deleta um guia de entrevista do usuário.
    """
    result = await interview_guide_service.delete_interview_guide_service(
        interview_guide_id, current_user
    )
    return result
