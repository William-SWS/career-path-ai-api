from fastapi import APIRouter, UploadFile, File, Depends, Query
from app.models.user import User
from app.services.resume_analysis_services import ResumeAnalysisService
from app.api.v1.dependencies.rate_limit import limit_ai_generation
from app.api.v1.dependencies.security import verify_token
from app.schemas.resume_analysis_schema import ResumeAnalysisResponse, ResumeAnalysisListResponse, ResumeAnalysisDeleteResponse
from app.api.v1.dependencies.services import get_resume_analysis_service


router = APIRouter()


@router.post("/", response_model=ResumeAnalysisResponse, dependencies=[Depends(limit_ai_generation)])
async def analyze_resume(
    file: UploadFile = File(...),
    current_user: User = Depends(verify_token),
    resume_analysis_service: ResumeAnalysisService = Depends(get_resume_analysis_service)
):
    """
    Faz análise do resumo enviado em .pdf e retorna para o usuário.
    """
    resume_analysis = await resume_analysis_service.analyze_resume_service(
        file, current_user
    )
    return resume_analysis


@router.get("/", response_model=ResumeAnalysisListResponse)
async def get_my_resume_analyses(
    current_user: User = Depends(verify_token),
    resume_analysis_service: ResumeAnalysisService = Depends(get_resume_analysis_service),
    skip: int = Query(0, ge=0, description="Número de itens para pular"),
    limit: int = Query(100, ge=1, le=100, description="Número máximo de itens por página")
):
    """
    Retorna todas as análises de currículo do usuário autenticado.
    """
    analyses = await resume_analysis_service.get_resume_analysis_service(
        current_user, skip, limit
    )
    return analyses
    

@router.get("/{analysis_id}", response_model=ResumeAnalysisResponse)
async def get_resume_analysis(
    analysis_id: int,
    current_user: User = Depends(verify_token),
    resume_analysis_service: ResumeAnalysisService = Depends(get_resume_analysis_service)
):
    """
    Retorna uma análise específica do usuário.
    """
    analysis = await resume_analysis_service.get_resume_analysis_by_id_service(
        analysis_id, current_user
    )
    return analysis


@router.delete("/{analysis_id}", response_model=ResumeAnalysisDeleteResponse)
async def delete_resume_analysis(
    analysis_id: int,
    current_user: User = Depends(verify_token),
    resume_analysis_service: ResumeAnalysisService = Depends(get_resume_analysis_service)
):
    """
    Deleta uma análise de currículo do usuário.
    """
    result = await resume_analysis_service.delete_resume_analysis_service(
        analysis_id, current_user
    )
    return result
