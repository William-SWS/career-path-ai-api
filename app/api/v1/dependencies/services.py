from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.llm.client import LLMClient, get_llm_client
from app.services.development_trail_services import DevelopmentTrailService
from app.services.interview_guide_services import InterviewGuideService
from app.services.resume_analysis_services import ResumeAnalysisService
from app.services.user_services import UserService


async def get_user_service(db: AsyncSession = Depends(get_db)) -> UserService:
    return UserService(db)


async def get_resume_analysis_service(
    db: AsyncSession = Depends(get_db),
    llm: LLMClient = Depends(get_llm_client),
) -> ResumeAnalysisService:
    return ResumeAnalysisService(db, llm)


async def get_interview_guide_service(
    db: AsyncSession = Depends(get_db),
    llm: LLMClient = Depends(get_llm_client),
) -> InterviewGuideService:
    return InterviewGuideService(db, llm)


async def get_development_trail_service(
    db: AsyncSession = Depends(get_db),
    llm: LLMClient = Depends(get_llm_client),
) -> DevelopmentTrailService:
    return DevelopmentTrailService(db, llm)
