from fastapi import APIRouter

from app.api.v1.routes import (
    auth_routes,
    health_routes,
    development_trail_routes,
    interview_guide_routes,
    resume_analysis_routes,
    user_routes,
)

router = APIRouter()

router.include_router(auth_routes.router, prefix="/auth", tags=["auth"])
router.include_router(health_routes.router, prefix="/check", tags=["check"])
router.include_router(
    interview_guide_routes.router, prefix="/interview-guide", tags=["interview-guide"]
)
router.include_router(
    development_trail_routes.router, prefix="/development-trail", tags=["development-trail"]
)
router.include_router(
    resume_analysis_routes.router, prefix="/resume-analysis", tags=["resume-analysis"]
)
router.include_router(user_routes.router, prefix="/users", tags=["users"])
