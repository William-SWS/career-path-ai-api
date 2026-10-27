from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.services.user_services import UserService
from app.services.resume_analysis_services import ResumeAnalysisService
from app.services.interview_guide_services import InterviewGuideService
from app.services.development_trail_services import DevelopmentTrailService


async def get_user_service(
    db: AsyncSession = Depends(get_db)
) -> UserService:
    return UserService(db)

async def get_resume_analysis_service(
    db: AsyncSession = Depends(get_db)
) -> ResumeAnalysisService:
    return ResumeAnalysisService(db)

async def get_interview_guide_service(
    db: AsyncSession = Depends(get_db)
) -> InterviewGuideService:
    return InterviewGuideService(db)

async def get_development_trail_service(
    db: AsyncSession = Depends(get_db)
) -> DevelopmentTrailService:
    return DevelopmentTrailService(db)
